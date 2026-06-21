// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights — Options GEX by-strike chart (Phase 1 / slice B)", () => {
  test("renders per-strike gamma bars when per_strike present", async ({ page }) => {
    await page.goto("/insights?tab=options&symbol=MU", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    await expect(page.getByTestId("options-gex-panel")).toBeVisible();
    const bars = page.getByTestId("gamma-bar-chart");
    await expect(bars).toBeVisible();
    // mock 提供 4 strikes
    await expect(page.getByTestId("gamma-bar")).toHaveCount(4);
  });
});
