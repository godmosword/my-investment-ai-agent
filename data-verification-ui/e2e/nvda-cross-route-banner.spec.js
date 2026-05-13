// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Bloomberg §6 — NVDA cross-route banner (mock BQ + divergent OHLC/quote)", () => {
  test("Insights shows mismatch banner and BQ vs yfinance note for NVDA", async ({ page }) => {
    await page.goto("/insights?e2e_symbols=NVDA", { waitUntil: "load" });
    const loading = page.getByText("載入終端…");
    if ((await loading.count()) > 0) {
      await loading.waitFor({ state: "hidden", timeout: 90_000 });
    }
    await expect(page.locator('[data-testid="terminal-workspace-grid"]')).toHaveAttribute(
      "data-active-symbols",
      /NVDA/,
      { timeout: 30_000 },
    );
    await expect(page.getByTestId("terminal-quote-last-NVDA")).toBeVisible({ timeout: 90_000 });
    const quoteText = await page.getByTestId("terminal-quote-last-NVDA").innerText();
    expect(quoteText.replace(/\s/g, "")).toMatch(/900\.125/);

    await expect(page.getByTestId("terminal-price-mismatch-banner-NVDA")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("terminal-price-mismatch-banner-NVDA")).toContainText("BigQuery");
    await expect(page.getByTestId("terminal-price-mismatch-banner-NVDA")).toContainText("yfinance");
  });
});
