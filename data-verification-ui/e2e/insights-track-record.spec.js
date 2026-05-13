// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights Track Record tab", () => {
  test("loads summary, closed rows, and tag slice", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });

    await page.getByTestId("insights-tab-track-record").click();
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-wl")).toContainText("2/1");
    await expect(page.getByTestId("track-record-hit-rate")).toContainText("+66.7%");
    await expect(page.getByTestId("track-record-closed-table").getByText("NVDA", { exact: true })).toBeVisible();
    await expect(page.getByText("ai-nvda-long-1")).toBeVisible();

    await page.getByTestId("track-record-tag-ai").click();
    await expect(page.getByTestId("track-record-closed-table").getByText("MSFT", { exact: true })).toBeVisible();
    await expect(page.getByTestId("track-record-closed-table").getByText("BTC", { exact: true })).toBeHidden();
  });
});
