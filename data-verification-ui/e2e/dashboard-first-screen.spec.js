// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Dashboard — first screen is 宏觀總覽 (ITER-P4-44A)", () => {
  test("first screen is macro grid or honest empty/loading, not workbench intro", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });

    const overview = page
      .locator(
        "[data-testid=macro-indicator-grid], [data-testid=macro-dashboard-loading], [data-testid=macro-dashboard-error], [data-testid=macro-indicator-empty]",
      )
      .first();
    await expect(overview).toBeVisible({ timeout: 60_000 });
    const overviewBox = await overview.boundingBox();
    expect(overviewBox).toBeTruthy();
    expect(overviewBox.y).toBeGreaterThanOrEqual(0);
    expect(overviewBox.y).toBeLessThan(720);

    await expect(page.getByTestId("workbench-primary-question")).toBeHidden();
    await expect(page.getByTestId("dashboard-workbench-intro").getByRole("link", { name: "觀點" })).toBeHidden();
    await expect(page.getByTestId("dashboard-workbench-intro").getByRole("link", { name: "持倉" })).toBeHidden();

    const health = page.getByTestId("workbench-data-health-chip");
    const healthCollapsed = await health.evaluate((el) => {
      const details = el.closest("details");
      return Boolean(details && !details.open);
    });
    expect(healthCollapsed).toBe(true);

    await page.getByTestId("dashboard-intro-toggle").click();
    await expect(page.getByTestId("workbench-primary-question")).toBeVisible();
    await expect(page.getByTestId("dashboard-workbench-intro").getByRole("link", { name: "觀點" })).toBeVisible();
    await expect(page.getByTestId("dashboard-workbench-intro").getByRole("link", { name: "持倉" })).toBeVisible();
    await expect(page.getByTestId("workbench-primary-question")).toContainText("工作台");
  });

  test("?tab=depth still opens compute and onchain panels", async ({ page }) => {
    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("dashboard-tab-depth")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("compute-memory-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("onchain-panel")).toBeVisible({ timeout: 60_000 });
  });
});
