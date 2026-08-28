// @ts-check
import { test, expect } from "@playwright/test";

function isReportsListPath(pathname) {
  return pathname === "/api/reports" || pathname === "/api/reports/";
}

test.describe("Insights — 今日建議 honesty (ITER-V2-008)", () => {
  test("empty reports list shows UNKNOWN empty, not fabricated recs", async ({ page }) => {
    await page.route(
      (url) => isReportsListPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: "[]",
        });
      },
    );

    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const empty = page.getByTestId("daily-brief-empty");
    await expect(empty).toBeVisible({ timeout: 60_000 });
    await expect(empty).toContainText("UNKNOWN：尚無今日建議");
    await expect(empty).not.toContainText("EPS");
    await expect(empty).not.toContainText("etf_flow");
    await expect(empty).not.toContainText("avg_risk_score");
    await expect(page.getByTestId("daily-brief-panel")).toHaveCount(0);
    await expect(page.getByTestId("daily-brief-error")).toHaveCount(0);
  });

  test("default mock brief shows dated panel with labeled AI take", async ({ page }) => {
    await page.goto("/insights?tab=daily", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const panel = page.getByTestId("daily-brief-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("daily-brief-date")).toHaveText("2026-05-09");
    const take = page.getByTestId("daily-brief-ai-interpretation");
    await expect(take).toContainText("AI 解讀");
    await expect(take).toContainText("e2e grok");
    await expect(panel).not.toContainText("EPS");
    await expect(panel).not.toContainText("etf_flow");
    await expect(panel).not.toContainText("avg_risk_score");
    await expect(panel).not.toContainText("LONG");
    await expect(panel).not.toContainText("SHORT");
    await expect(page.getByTestId("daily-brief-report-link")).toHaveAttribute("href", "/report/2026-05-09");
    await expect(page.getByTestId("daily-brief-workspace-note")).toContainText("不是今日建議");
  });

  test("reports list 500 shows error, not empty", async ({ page }) => {
    await page.route(
      (url) => isReportsListPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "e2e reports list fail" }),
        });
      },
    );

    await page.goto("/insights?tab=daily", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const err = page.getByTestId("daily-brief-error");
    await expect(err).toBeVisible({ timeout: 60_000 });
    await expect(err).toContainText("今日建議暫時無法載入。");
    await expect(page.getByTestId("daily-brief-empty")).toHaveCount(0);
    await expect(page.getByTestId("daily-brief-panel")).toHaveCount(0);
  });
});
