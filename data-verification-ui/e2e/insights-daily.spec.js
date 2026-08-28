// @ts-check
import { test, expect } from "@playwright/test";

function isReportsList(url) {
  const path = url.pathname;
  return path === "/api/reports" || path === "/api/reports/";
}

test.describe("Insights — 今日建議 honesty (ITER-V2-008)", () => {
  test("default mock shows brief date, payload thesis, and labeled AI 解讀", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("daily-brief-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("daily-brief-date")).toHaveText("2026-05-09");
    await expect(page.getByTestId("daily-brief-ai-interpretation")).toContainText("AI 解讀");
    await expect(page.getByTestId("daily-brief-ai-interpretation")).toContainText("e2e grok");
    await expect(page.getByTestId("daily-brief-thesis")).toContainText("e2e structured thesis");
    await expect(page.getByTestId("daily-brief-exec-summary")).toContainText("e2e structured bullet");
    await expect(page.getByTestId("daily-brief-report-link")).toHaveAttribute("href", "/report/2026-05-09");
    await expect(page.getByTestId("daily-brief-empty")).toHaveCount(0);
    await expect(page.getByTestId("daily-brief-workspace-note")).toContainText("不是今日建議");
  });

  test("empty reports list shows UNKNOWN and does not invent numbers", async ({ page }) => {
    await page.route((url) => isReportsList(url), async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    const empty = page.getByTestId("daily-brief-empty");
    await expect(empty).toBeVisible({ timeout: 60_000 });
    await expect(empty).toContainText("UNKNOWN：尚無今日建議");
    await expect(page.getByTestId("daily-brief-panel")).toHaveCount(0);
    await expect(empty).not.toContainText("EPS");
    await expect(empty).not.toContainText("etf_flow");
  });

  test("reports list error is distinct from empty", async ({ page }) => {
    await page.route((url) => isReportsList(url), async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: "{\"detail\":\"fail\"}" });
    });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("daily-brief-error")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("daily-brief-empty")).toHaveCount(0);
    await expect(page.getByTestId("daily-brief-panel")).toHaveCount(0);
  });
});
