// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Dashboard route /dashboard (Queue 39)", () => {
  test("loads macro snapshot cards, catalysts, and BTC alignment strip", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });

    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("macro-indicator-grid")).toBeVisible();
    await expect(page.locator('article[data-testid^="macro-indicator-"]')).toHaveCount(8);
    await expect(page.getByTestId("macro-indicator-btc")).toContainText("BTC");
    await expect(page.getByTestId("macro-indicator-next_fed_cpi")).toContainText("US CPI");
    await expect(page.getByTestId("catalyst-calendar")).toContainText("US CPI");
    await expect(page.getByTestId("macro-regime-panel")).toContainText("RISK ON");
    await expect(page.getByTestId("today-btc-quote-last")).toContainText(/50,000\.125/);
  });
});
