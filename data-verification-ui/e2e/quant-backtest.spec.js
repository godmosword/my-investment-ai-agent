import { expect, test } from "@playwright/test";

test.describe("Quant backtest panel", () => {
  test("renders paper-derived backtest metrics on insights signals tab", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await page.getByTestId("insights-tab-signals").click();
    await expect(page.getByTestId("backtest-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("backtest-panel")).toContainText("Backtest");
    await expect(page.getByTestId("backtest-panel")).toContainText("總報酬");
    await expect(page.getByTestId("backtest-panel")).toContainText("Sharpe");
  });
});
