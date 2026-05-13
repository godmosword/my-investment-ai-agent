// @ts-check
import { test, expect } from "@playwright/test";

async function waitTerminalReady(page, activeSymbolsPattern) {
  const loading = page.getByText("載入終端…");
  if ((await loading.count()) > 0) {
    await loading.waitFor({ state: "hidden", timeout: 90_000 });
  }
  await expect(page.locator('[data-testid="terminal-workspace-grid"]')).toHaveAttribute(
    "data-active-symbols",
    activeSymbolsPattern,
    { timeout: 30_000 },
  );
}

test.describe("Insights T1/T2 state matrix", () => {
  test("keeps snapshot content when quote fails for one symbol", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("e2e_quote_fail_symbols", "SPY");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/insights?e2e_symbols=BTC,SPY", { waitUntil: "load" });
    await waitTerminalReady(page, /BTC.*SPY|SPY.*BTC/);

    await expect(page.getByTestId("terminal-quote-degraded-SPY")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("terminal-report-links-SPY")).toBeVisible();
    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible();
  });

  test("one snapshot failure does not blank the other cards", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("e2e_snapshot_fail_symbols", "SPY");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/insights?e2e_symbols=BTC,SPY", { waitUntil: "load" });
    await waitTerminalReady(page, /BTC.*SPY|SPY.*BTC/);

    await expect(page.getByTestId("terminal-snapshot-error-SPY")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible();
    await expect(page.getByTestId("terminal-snapshot-error-BTC")).toHaveCount(0);
  });

  test("shows N/A alignment state when backend returns aligned=null", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("e2e_btc_alignment_na", "1");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/insights?e2e_btc=1", { waitUntil: "load" });
    await waitTerminalReady(page, /BTC/);

    await expect(page.getByTestId("terminal-price-alignment-status-BTC")).toContainText(/對齊狀態：N\/A/);
    await expect(page.getByTestId("terminal-price-mismatch-banner-BTC")).toHaveCount(0);
  });
});
