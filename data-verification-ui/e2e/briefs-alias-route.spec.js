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

test.describe("/briefs alias", () => {
  test("loads same terminal workspace as /terminal", async ({ page }) => {
    await page.goto("/briefs?e2e_symbols=BTC", { waitUntil: "load" });
    await waitTerminalReady(page, /BTC/);
    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible({ timeout: 60_000 });
  });
});
