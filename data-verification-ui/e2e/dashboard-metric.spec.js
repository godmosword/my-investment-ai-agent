// @ts-check
import { test, expect } from "@playwright/test";

function isStructuredPath(pathname) {
  return /^\/api\/reports\/\d{4}-\d{2}-\d{2}\/structured$/.test(pathname);
}

function structuredLegacy(legacy) {
  return {
    report_date: "2026-04-14",
    profile: "full",
    block_ids: [],
    block_registry: {},
    daily_brief_report: null,
    structured_body_available: false,
    gate_summary: {
      available: false,
      ok: null,
      issues: [],
      issues_by_block: {},
      issues_unmapped: [],
    },
    legacy: {
      timestamp: "2026-04-14T00:00:00Z",
      ...legacy,
    },
  };
}

/** @param {import("@playwright/test").Page} page */
function cardValue(page, label) {
  return page.getByTestId("metric-card").filter({ hasText: label }).getByTestId("metric-card-value");
}

test.describe("MetricCard honesty (report metrics)", () => {
  test("default DXY is a finite number, not UNKNOWN or em dash", async ({ page }) => {
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });
    await expect(cardValue(page, "DXY")).toHaveText("100.00");
    await expect(cardValue(page, "DXY")).not.toHaveText("UNKNOWN");
    await expect(cardValue(page, "DXY")).not.toHaveText("—");
  });

  test("null / omitted / non-finite metric values are UNKNOWN, not em dash", async ({ page }) => {
    await page.route(
      (url) => isStructuredPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            structuredLegacy({
              dxy: null,
              etf_flow_millions: "n/a",
              mvrv_z_score: undefined,
              avg_risk_score: "",
            }),
          ),
        });
      },
    );
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });
    await expect(cardValue(page, "DXY")).toHaveText("UNKNOWN");
    await expect(cardValue(page, "ETF 資金流")).toHaveText("UNKNOWN");
    await expect(cardValue(page, "MVRV Z")).toHaveText("UNKNOWN");
    await expect(cardValue(page, "風險評分")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("metric-card").first()).not.toContainText("—");
  });

  test("finite 0 still displays", async ({ page }) => {
    await page.route(
      (url) => isStructuredPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            structuredLegacy({
              dxy: 0,
              etf_flow_millions: 0,
              mvrv_z_score: 0,
              avg_risk_score: 0,
            }),
          ),
        });
      },
    );
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });
    await expect(cardValue(page, "DXY")).toHaveText("0.00");
    await expect(cardValue(page, "ETF 資金流")).toHaveText("0");
    await expect(cardValue(page, "MVRV Z")).toHaveText("0.00");
    await expect(cardValue(page, "風險評分")).toHaveText("0.0");
    await expect(cardValue(page, "DXY")).not.toHaveText("UNKNOWN");
    await expect(cardValue(page, "DXY")).not.toHaveText("—");
  });
});
