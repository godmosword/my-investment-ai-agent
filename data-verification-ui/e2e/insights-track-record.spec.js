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

    const deepDive = page.getByTestId("track-record-action-deep-dive").first();
    await expect(deepDive).toBeVisible();
    await deepDive.click();
    await expect(page).toHaveURL(/\/insights\?symbol=NVDA/i);

    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    const monitor = page.getByTestId("track-record-action-monitor").first();
    await expect(monitor).toBeVisible();
    await monitor.click();
    await expect(page).toHaveURL(/\/portfolio\?tab=monitor.*focus=NVDA/i);

    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("track-record-tag-ai").click();
    await expect(page.getByTestId("track-record-closed-table").getByText("MSFT", { exact: true })).toBeVisible();
    await expect(page.getByTestId("track-record-closed-table").getByText("BTC", { exact: true })).toBeHidden();
  });

  test("equity curve renders as themed chart (VU2)", async ({ page }) => {
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    const chart = page.getByTestId("equity-curve-chart");
    await expect(chart).toBeVisible();
    await expect(chart.locator("canvas").first()).toBeVisible();
  });

  test("empty paper outcomes show setup guidance before zero KPIs", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_closed: 0,
          wins: 0,
          losses: 0,
          flats: 0,
          hit_rate_pct: 0,
          avg_return_pct: 0,
          sharpe: 0,
          max_drawdown_pct: 0,
          cumulative_return_pct: 0,
          equity_curve: [],
          source: "execution_intents.jsonl",
          source_row_count: 0,
        }),
      });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          summary: { total_closed: 0, equity_curve: [] },
          records: [],
          total: 0,
          limit: 50,
          offset: 0,
          source: "execution_intents.jsonl",
        }),
      });
    });

    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-empty-guidance")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-empty-guidance")).toContainText("還缺 closed paper signals");
  });
});
