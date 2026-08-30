// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Portfolio — first screen is 總覽 (ITER-P4-44A)", () => {
  test("first screen is overview KPIs/holdings, not workbench intro or health chip", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const overview = page
      .locator(
        "[data-testid=portfolio-total-value], [data-testid^=portfolio-holding-card-], [data-testid=portfolio-holdings-table]",
      )
      .first();
    await expect(overview).toBeVisible({ timeout: 60_000 });
    const overviewBox = await overview.boundingBox();
    expect(overviewBox).toBeTruthy();
    expect(overviewBox.y).toBeGreaterThanOrEqual(0);
    expect(overviewBox.y).toBeLessThan(720);

    await expect(page.getByTestId("workbench-primary-question")).toBeHidden();
    await expect(page.getByTestId("workbench-data-health-chip")).toBeHidden();

    const health = page.getByTestId("workbench-data-health-chip");
    const healthCollapsed = await health.evaluate((el) => {
      const details = el.closest("details");
      return Boolean(details && !details.open);
    });
    expect(healthCollapsed).toBe(true);

    await page.getByTestId("portfolio-intro-toggle").click();
    await expect(page.getByTestId("workbench-primary-question")).toBeVisible();
    await expect(page.getByTestId("workbench-data-health-chip")).toBeVisible();
    await expect(page.getByTestId("workbench-primary-question")).toContainText("工作台");
  });

  test("?tab=monitor still opens WatchlistMonitor", async ({ page }) => {
    await page.goto("/portfolio?tab=monitor", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("portfolio-tab-monitor")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("watchlist-monitor")).toBeVisible({ timeout: 60_000 });
  });

  test("?tab=risk still opens PortfolioRiskPanel", async ({ page }) => {
    await page.goto("/portfolio?tab=risk", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("portfolio-tab-risk")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });
  });
});
