// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights — Options Flow + GEX tab (F1)", () => {
  test("watchlist strip shows GEX regime + unusual counts", async ({ page }) => {
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    const strip = page.getByTestId("options-watchlist");
    await expect(strip.locator('[data-symbol="MU"]')).toBeVisible();
    await expect(strip.locator('[data-symbol="NVDA"]')).toBeVisible();
    await expect(strip.getByText("MU", { exact: false })).toBeVisible();
  });

  test("selecting a symbol shows GEX panel + unusual flow rows", async ({ page }) => {
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    await page.locator('[data-testid="options-watchlist-chip"][data-symbol="MU"]').click();
    await expect(page.getByTestId("options-gex-panel")).toBeVisible();
    await expect(page.getByTestId("options-gex-panel").getByText("MU", { exact: true })).toBeVisible();

    const flow = page.getByTestId("options-flow-table");
    await expect(flow).toBeVisible();
    await expect(flow.getByTestId("options-flow-row").first()).toBeVisible();
    await expect(flow.getByText("volume_oi", { exact: false })).toBeVisible();
  });

  test("symbol query param drives the URL on selection", async ({ page }) => {
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    await page.locator('[data-testid="options-watchlist-chip"][data-symbol="NVDA"]').click();
    await expect(page).toHaveURL(/symbol=NVDA/);
    await expect(page.getByTestId("options-gex-panel").getByText("NVDA", { exact: true })).toBeVisible();
  });
});
