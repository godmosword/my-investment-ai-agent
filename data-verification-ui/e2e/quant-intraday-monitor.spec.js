import { expect, test } from "@playwright/test";

test.describe("Quant Intraday Monitor", () => {
  test("renders paper-derived rows with live quote and deep-links to symbol view", async ({ page }) => {
    await page.goto("/insights?tab=signals", { waitUntil: "load" });

    const monitor = page.getByTestId("quant-intraday-monitor");
    await expect(monitor).toBeVisible({ timeout: 60_000 });
    await expect(monitor).toContainText("Intraday");

    const nvdaRow = page.locator('[data-testid="quant-intraday-row"][data-symbol="NVDA"]');
    await expect(nvdaRow).toBeVisible();
    await expect(nvdaRow).toContainText("NVDA");
    await expect(nvdaRow).toContainText("PAPER_FILLED");
    await expect(nvdaRow.getByTestId("quant-intraday-price")).not.toHaveText("—", { timeout: 30_000 });

    await page.getByTestId("quant-intraday-filter").fill("NV");
    await expect(page.getByTestId("quant-intraday-row")).toHaveCount(1);

    await nvdaRow.click();
    await expect(page).toHaveURL(/\/insights\?symbol=NVDA/);
  });
});
