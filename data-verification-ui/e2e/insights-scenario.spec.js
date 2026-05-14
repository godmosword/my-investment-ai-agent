import { test, expect } from "@playwright/test";

test.describe("Insights scenario tab (queue 28d UI)", () => {
  test("shows scenario cards from mock API", async ({ page }) => {
    await page.goto("/insights?tab=scenario");
    await expect(page.getByTestId("insights-tab-scenario")).toBeVisible();
    await expect(page.getByTestId("scenario-planner-home")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("scenario-card-defensive")).toBeVisible();
    await expect(page.getByTestId("scenario-card-base")).toBeVisible();
  });
});
