import { expect, test } from "@playwright/test";

test.describe("Insights paper lifecycle", () => {
  test("renders paper lifecycle summary, table, create form, and blotter", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await page.getByTestId("insights-tab-paper").click();

    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("paper-kpi-active")).toContainText("1");
    await expect(page.getByTestId("paper-kpi-realized")).toContainText("+10.0%");
    await expect(page.getByTestId("paper-kpi-quality")).toContainText("78.5");
    await expect(page.getByTestId("paper-quality-vs-pnl")).toContainText("A: +12.0%");
    await expect(page.getByTestId("paper-transparency-letter")).toContainText("Monthly Transparency Letter");
    await expect(page.getByTestId("paper-letter-publishable")).toContainText("sample 1/5");
    await expect(page.getByTestId("paper-lifecycle-table").getByText("NVDA", { exact: true })).toBeVisible();
    await expect(page.getByTestId("paper-quality-badge").first()).toContainText("A");
    await expect(page.getByTestId("paper-intent-create-toggle")).toBeVisible();
    await expect(page.getByText("執行意圖（紙上前置）")).toBeVisible();
    await expect(page.getByTestId("intent-quality-badge").first()).toContainText("D");
    await page.getByTestId("intent-quality-filter").selectOption("D");
    await expect(page.getByText("e2e-spy-1")).toBeVisible();

    await page.getByTestId("paper-intent-create-toggle").click();
    await page.getByTestId("paper-intent-asset").fill("msft");
    await page.getByTestId("paper-intent-create-submit").click();
    await expect(page.getByTestId("paper-intent-create-toggle")).toContainText("+ 新增意圖");
  });
});

function isPaperSummaryPath(pathname) {
  return pathname === "/api/paper/lifecycle" || pathname === "/api/paper/pnl";
}

test.describe("Insights paper lifecycle honesty (ITER-V2-009)", () => {
  test("missing summary shows empty UNKNOWN, not fabricated 0 Active/Closed", async ({ page }) => {
    await page.route(
      (url) => isPaperSummaryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ as_of: "2026-05-13T00:00:00Z", source: "e2e", rows: [] }),
        });
      },
    );
    await page.goto("/insights?tab=paper", { waitUntil: "load" });
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    const empty = page.getByTestId("paper-lifecycle-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("UNKNOWN：尚無紙上生命週期摘要");
    await expect(page.getByTestId("paper-kpi-active")).toHaveCount(0);
    await expect(page.getByTestId("paper-kpi-closed")).toHaveCount(0);
    await expect(empty).not.toContainText("0 Active");
  });

  test("summary error is distinct from empty and does not show fake 0 KPIs", async ({ page }) => {
    await page.route(
      (url) => isPaperSummaryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "e2e paper fail" }),
        });
      },
    );
    await page.goto("/insights?tab=paper", { waitUntil: "load" });
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("paper-lifecycle-error")).toBeVisible();
    await expect(page.getByTestId("paper-lifecycle-empty")).toHaveCount(0);
    await expect(page.getByTestId("paper-kpi-active")).toHaveCount(0);
  });

  test("missing quality_grade and numbers are UNKNOWN; quote_error stays visible", async ({ page }) => {
    await page.route(
      (url) => isPaperSummaryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            as_of: "2026-05-13T00:00:00Z",
            source: "e2e",
            summary: {
              total: 1,
              active_count: 1,
              closed_count: 0,
              wins: 0,
              losses: 0,
              avg_realized_return_pct: null,
              avg_quality_score: null,
            },
            rows: [
              {
                signal_id: "e2e-missing-grade",
                asset: "TSM",
                direction: "LONG",
                status: "APPROVED_FOR_PAPER",
                entry_price: null,
                mark_price: null,
                return_pct: null,
                quality_score: null,
                quote_error: "timeout",
              },
            ],
          }),
        });
      },
    );
    await page.goto("/insights?tab=paper", { waitUntil: "load" });
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("paper-kpi-realized")).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("paper-kpi-quality")).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("paper-quality-badge").first()).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("paper-quality-badge").first()).not.toContainText("D");
    await expect(page.getByTestId("paper-lifecycle-table")).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("paper-lifecycle-table")).toContainText("quote unavailable");
    await expect(page.getByTestId("paper-kpi-realized")).not.toContainText("0%");
  });

  test("empty lifecycle table copy is 列, not rows", async ({ page }) => {
    await page.route(
      (url) => isPaperSummaryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            as_of: "2026-05-13T00:00:00Z",
            source: "e2e",
            summary: {
              total: 0,
              active_count: 0,
              closed_count: 0,
              wins: 0,
              losses: 0,
              avg_realized_return_pct: 0,
              avg_quality_score: 0,
            },
            rows: [],
          }),
        });
      },
    );
    await page.goto("/insights?tab=paper", { waitUntil: "load" });
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    const emptyTable = page.getByTestId("paper-lifecycle-table-empty");
    await expect(emptyTable).toHaveText("目前沒有紙上生命週期列。");
    await expect(emptyTable).not.toContainText("rows");
  });

  test("missing category and thesis_one_liner are UNKNOWN, not em dash", async ({ page }) => {
    await page.route(
      (url) => isPaperSummaryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            as_of: "2026-05-13T00:00:00Z",
            source: "e2e",
            summary: {
              total: 3,
              active_count: 3,
              closed_count: 0,
              wins: 0,
              losses: 0,
              avg_realized_return_pct: 0,
              avg_quality_score: 70,
            },
            rows: [
              {
                signal_id: "e2e-missing",
                asset: "AAA",
                direction: "LONG",
                status: "APPROVED_FOR_PAPER",
              },
              {
                signal_id: "e2e-blank",
                asset: "BBB",
                direction: "SHORT",
                status: "APPROVED_FOR_PAPER",
                category: "   ",
                thesis_one_liner: "   ",
              },
              {
                signal_id: "e2e-ok",
                asset: "CCC",
                direction: "LONG",
                status: "APPROVED_FOR_PAPER",
                category: "AI",
                thesis_one_liner: "real thesis",
              },
            ],
          }),
        });
      },
    );
    await page.goto("/insights?tab=paper", { waitUntil: "load" });
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    const table = page.getByTestId("paper-lifecycle-table");
    await expect(table).toBeVisible();
    const categories = table.getByTestId("paper-row-category");
    const theses = table.getByTestId("paper-row-thesis");
    await expect(categories).toHaveCount(3);
    await expect(categories.nth(0)).toHaveText("UNKNOWN");
    await expect(categories.nth(1)).toHaveText("UNKNOWN");
    await expect(categories.nth(2)).toHaveText("AI");
    await expect(theses.nth(0)).toHaveText("UNKNOWN");
    await expect(theses.nth(1)).toHaveText("UNKNOWN");
    await expect(theses.nth(2)).toHaveText("real thesis");
    await expect(table).not.toContainText("—");
  });

  test("publishable transparency letter shows 樣本就緒", async ({ page }) => {
    await page.route("**/api/paper/transparency-letter*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          month: "2026-05",
          source: "e2e",
          summary: { closed_count: 5, min_publishable_sample: 5, publishable: true },
          alignment: {},
          letter_markdown: "e2e",
        }),
      });
    });
    await page.goto("/insights?tab=paper", { waitUntil: "load" });
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    const badge = page.getByTestId("paper-letter-publishable");
    await expect(badge).toHaveText("樣本就緒");
    await expect(badge).not.toContainText("sample ready");
  });

  test("transparency letter missing month shows UNKNOWN, not current month", async ({ page }) => {
    await page.route("**/api/paper/transparency-letter*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          source: "e2e",
          summary: { closed_count: 1, min_publishable_sample: 5, publishable: false },
          alignment: {},
          letter_markdown: "e2e",
        }),
      });
    });
    await page.goto("/insights?tab=paper", { waitUntil: "load" });
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    const month = page.getByTestId("paper-letter-month");
    await expect(month).toHaveText("UNKNOWN");
    await expect(page.getByTestId("paper-transparency-letter")).not.toContainText("current month");
  });
});
