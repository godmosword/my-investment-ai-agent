// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Terminal — SPY price_alignment mismatch + gate hint", () => {
  test("shows mismatch banner for SPY and gate-related hint on intent row", async ({ page }) => {
    await page.goto("/terminal?e2e_symbols=BTC,SPY", { waitUntil: "load" });
    const loading = page.getByText("載入終端…");
    if ((await loading.count()) > 0) {
      await loading.waitFor({ state: "hidden", timeout: 90_000 });
    }
    await expect(page.locator('[data-testid="terminal-workspace-grid"]')).toHaveAttribute(
      "data-active-symbols",
      /BTC.*SPY|SPY.*BTC/,
      { timeout: 30_000 },
    );

    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible({ timeout: 90_000 });
    await expect(page.getByTestId("terminal-quote-last-SPY")).toBeVisible({ timeout: 30_000 });
    const spyQuote = await page.getByTestId("terminal-quote-last-SPY").innerText();
    expect(spyQuote.replace(/\s/g, "")).toMatch(/610\.25/);

    await expect(page.getByTestId("terminal-price-mismatch-banner-SPY")).toBeVisible({ timeout: 30_000 });

    await expect(page.getByText("Gate 關聯：")).toBeVisible({ timeout: 15_000 });
  });

  test("internal report link navigates to Report route", async ({ page }) => {
    await page.goto("/terminal?e2e_symbols=SPY", { waitUntil: "load" });
    const loading = page.getByText("載入終端…");
    if ((await loading.count()) > 0) {
      await loading.waitFor({ state: "hidden", timeout: 90_000 });
    }
    await expect(page.getByTestId("terminal-report-links-SPY")).toBeVisible({ timeout: 90_000 });
    await page.getByTestId("terminal-report-links-SPY").getByRole("link", { name: "2026-04-14" }).click();
    await expect(page).toHaveURL(/\/report\/2026-04-14/, { timeout: 30_000 });
  });
});
