// @ts-check
import { test, expect } from "@playwright/test";

async function waitTerminalReady(page, activeSymbolsPattern) {
  const workspace = page.getByTestId("daily-brief-workspace");
  await workspace.waitFor({ state: "attached", timeout: 60_000 });
  await workspace.evaluate((el) => {
    if (el instanceof HTMLDetailsElement) el.open = true;
  });
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

test.describe("legacy terminal aliases", () => {
  test("/ redirects to /insights and keeps query params", async ({ page }) => {
    await page.goto("/?e2e_symbols=BTC", { waitUntil: "load" });
    await expect(page).toHaveURL(/\/insights\?e2e_symbols=BTC/);
    await waitTerminalReady(page, /BTC/);
    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible({ timeout: 60_000 });
  });

  test("/briefs redirects to /insights and keeps query params", async ({ page }) => {
    await page.goto("/briefs?e2e_symbols=BTC", { waitUntil: "load" });
    await expect(page).toHaveURL(/\/insights\?e2e_symbols=BTC/);
    await waitTerminalReady(page, /BTC/);
    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible({ timeout: 60_000 });
  });

  test("/terminal redirects to /insights and keeps query params", async ({ page }) => {
    await page.goto("/terminal?e2e_symbols=BTC", { waitUntil: "load" });
    await expect(page).toHaveURL(/\/insights\?e2e_symbols=BTC/);
    await waitTerminalReady(page, /BTC/);
    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible({ timeout: 60_000 });
  });
});
