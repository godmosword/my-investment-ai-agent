// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights Track Record tab", () => {
  test("tab visible copy is 實績, not Track Record", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    const tab = page.getByTestId("insights-tab-track-record");
    await expect(tab).toBeVisible({ timeout: 60_000 });
    await expect(tab).toHaveText("實績");
    await expect(tab).not.toHaveText("Track Record");
  });

  test("page title is 實績, not Track Record", async ({ page }) => {
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    const title = page.getByTestId("track-record-home").locator(".page-title");
    await expect(title).toHaveText("實績");
    await expect(title).not.toHaveText("Track Record");
    await expect(page.getByTestId("track-record-home").locator(".page-subtitle")).toHaveText(
      "僅紙上結果 · 來源可稽核",
    );
  });

  test("KPI labels are 勝／負 命中率 平均報酬 最大回撤; Sharpe stays", async ({ page }) => {
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-wl").locator(".metric-label")).toHaveText("勝／負");
    await expect(page.getByTestId("track-record-hit-rate").locator(".metric-label")).toHaveText("命中率");
    await expect(page.getByTestId("track-record-avg-return").locator(".metric-label")).toHaveText("平均報酬");
    await expect(page.getByTestId("track-record-max-dd").locator(".metric-label")).toHaveText("最大回撤");
    await expect(page.getByTestId("track-record-sharpe").locator(".metric-label")).toHaveText("Sharpe");
    await expect(page.getByTestId("track-record-cumulative").locator(".metric-label")).toHaveText("累積");
    await expect(page.getByTestId("track-record-wl")).toContainText("3 已結");
    await expect(page.getByTestId("track-record-wl")).not.toContainText("closed");
    await expect(page.getByTestId("track-record-home")).not.toContainText("W / L");
    await expect(page.getByTestId("track-record-home")).not.toContainText("Hit Rate");
    await expect(page.getByTestId("track-record-home")).not.toContainText("Avg Return");
    await expect(page.getByTestId("track-record-home")).not.toContainText("Max DD");
    await expect(page.getByTestId("track-record-home")).not.toContainText("Total");
  });

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

  test("closed card count is 筆, not rows", async ({ page }) => {
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    const count = page.getByTestId("track-record-closed-count");
    await expect(count).toHaveText("3 筆");
    await expect(count).not.toContainText("rows");
    await expect(page.getByTestId("track-record-closed-card")).not.toContainText("rows");
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
    const guidance = page.getByTestId("track-record-empty-guidance");
    await expect(guidance).toContainText("還缺已結紙上訊號");
    await expect(guidance).toContainText("實績需要已關閉的紙上意圖");
    await expect(guidance).toContainText("市價結算列");
    await expect(guidance).toContainText("recommendation_outcomes");
    await expect(guidance).toContainText("scripts/mark_recommendations.py");
    await expect(guidance).not.toContainText("closed paper signals");
    await expect(guidance).not.toContainText("mark-to-market");
    await expect(guidance).not.toContainText("paper intent");
    await expect(guidance).not.toContainText("Track Record");
    await expect(page.getByTestId("track-record-closed-card")).toContainText("尚無可計算的已結紙上訊號。");
    await expect(page.getByTestId("track-record-closed-card")).not.toContainText("closed paper signal");
  });

  test("loading copy is 載入實績…, not Track Record", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 8_000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_closed: 0,
          wins: 0,
          losses: 0,
          equity_curve: [],
          source: "e2e",
        }),
      });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 8_000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ records: [], total: 0, limit: 50, offset: 0, source: "e2e" }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "domcontentloaded" });
    const loading = page.getByTestId("track-record-loading");
    await expect(loading).toBeVisible({ timeout: 5_000 });
    await expect(loading).toHaveText("載入實績…");
    await expect(loading).not.toContainText("Track Record");
    await expect(page.getByTestId("track-record-home")).not.toContainText("Track Record");
  });
});

test.describe("Insights Track Record honesty (ITER-V2-010)", () => {
  test("missing summary is UNKNOWN empty, not fabricated 0/0 or 0.0%", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "null" });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ records: [], total: 0, limit: 50, offset: 0 }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-unknown-empty")).toBeVisible();
    await expect(page.getByTestId("track-record-unknown-empty")).toHaveText("UNKNOWN：尚無實績摘要");
    await expect(page.getByTestId("track-record-home")).not.toContainText("Track Record");
    await expect(page.getByTestId("track-record-wl")).toHaveCount(0);
    await expect(page.getByTestId("track-record-hit-rate")).toHaveCount(0);
    await expect(page.getByTestId("track-record-empty-guidance")).toHaveCount(0);
    await expect(page.getByTestId("track-record-home")).not.toContainText("0/0");
    await expect(page.getByTestId("track-record-home")).not.toContainText("0.0%");
  });

  test("without summary does not render 累積曲線 card; UNKNOWN empty remains", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "null" });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ records: [], total: 0, limit: 50, offset: 0 }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-unknown-empty")).toBeVisible();
    await expect(page.getByTestId("track-record-unknown-empty")).toContainText("UNKNOWN");
    await expect(page.getByTestId("track-record-equity-card")).toHaveCount(0);
    await expect(page.getByTestId("equity-curve-chart")).toHaveCount(0);
    await expect(page.getByTestId("track-record-home")).not.toContainText("累積曲線");
  });

  test("without summary does not render 閉倉紀錄 card", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "null" });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ records: [], total: 0, limit: 50, offset: 0 }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-unknown-empty")).toBeVisible();
    await expect(page.getByTestId("track-record-unknown-empty")).toContainText("UNKNOWN");
    await expect(page.getByTestId("track-record-closed-card")).toHaveCount(0);
    await expect(page.getByTestId("track-record-closed-table")).toHaveCount(0);
    await expect(page.getByTestId("track-record-home")).not.toContainText("閉倉紀錄");
  });

  test("summary error is distinct from empty and does not fake 0 KPIs", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: "{\"detail\":\"fail\"}" });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: "{\"detail\":\"fail\"}" });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-error")).toBeVisible();
    await expect(page.getByTestId("track-record-error")).toHaveText("實績暫時無法載入。");
    await expect(page.getByTestId("track-record-home")).not.toContainText("Track Record");
    await expect(page.getByTestId("track-record-wl")).toHaveCount(0);
    await expect(page.getByTestId("track-record-empty-guidance")).toHaveCount(0);
  });

  test("non-finite KPI fields show UNKNOWN／未提供, not 0.0% / 0.00", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_closed: 2,
          wins: 1,
          losses: 1,
          hit_rate_pct: null,
          avg_return_pct: null,
          sharpe: null,
          max_drawdown_pct: "n/a",
          cumulative_return_pct: null,
          equity_curve: [],
          source: "e2e",
        }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-wl")).toContainText("1/1");
    await expect(page.getByTestId("track-record-hit-rate")).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("track-record-sharpe")).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("track-record-max-dd")).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("track-record-hit-rate")).not.toContainText("0.0%");
    await expect(page.getByTestId("track-record-sharpe")).not.toContainText("0.00");
  });

  test("row without asset has no Deep dive or Monitor link", async ({ page }) => {
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          summary: { total_closed: 1 },
          records: [{ signal_id: "e2e-no-asset", outcome: "win", direction: "LONG" }],
          total: 1,
          limit: 50,
          offset: 0,
          source: "e2e",
        }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-closed-table")).toBeVisible();
    await expect(page.getByTestId("track-record-action-deep-dive")).toHaveCount(0);
    await expect(page.getByTestId("track-record-action-monitor")).toHaveCount(0);
  });

  test("missing category and closed_at are UNKNOWN, not em dash; date prefix stays", async ({ page }) => {
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_closed: 3,
          wins: 2,
          losses: 1,
          hit_rate_pct: 66.7,
          avg_return_pct: 1,
          sharpe: 1,
          max_drawdown_pct: -1,
          cumulative_return_pct: 1,
          equity_curve: [],
          source: "e2e",
        }),
      });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          summary: { total_closed: 3 },
          records: [
            { signal_id: "e2e-missing", asset: "AAA", outcome: "win", direction: "LONG" },
            {
              signal_id: "e2e-blank",
              asset: "BBB",
              outcome: "loss",
              direction: "SHORT",
              category: "   ",
              closed_at: "   ",
            },
            {
              signal_id: "e2e-ok",
              asset: "CCC",
              outcome: "win",
              direction: "LONG",
              category: "AI",
              closed_at: "2026-05-13T12:00:00Z",
            },
          ],
          total: 3,
          limit: 50,
          offset: 0,
          source: "e2e",
        }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    const table = page.getByTestId("track-record-closed-table");
    await expect(table).toBeVisible();
    const categories = table.getByTestId("track-record-row-category");
    const closedAts = table.getByTestId("track-record-row-closed-at");
    await expect(categories).toHaveCount(3);
    await expect(categories.nth(0)).toHaveText("UNKNOWN");
    await expect(categories.nth(1)).toHaveText("UNKNOWN");
    await expect(categories.nth(2)).toHaveText("AI");
    await expect(closedAts.nth(0)).toHaveText("UNKNOWN");
    await expect(closedAts.nth(1)).toHaveText("UNKNOWN");
    await expect(closedAts.nth(2)).toHaveText("2026-05-13");
    await expect(table).not.toContainText("—");
  });

  test("equity source missing or blank is UNKNOWN, not em dash; real source stays", async ({ page }) => {
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("track-record-equity-source")).toHaveText("execution_intents.jsonl");

    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_closed: 1,
          wins: 1,
          losses: 0,
          hit_rate_pct: 100,
          avg_return_pct: 1,
          sharpe: 1,
          max_drawdown_pct: -1,
          cumulative_return_pct: 1,
          equity_curve: [],
        }),
      });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          summary: { total_closed: 1 },
          records: [{ signal_id: "e2e-src-missing", asset: "AAA", outcome: "win", direction: "LONG" }],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    const missing = page.getByTestId("track-record-equity-source");
    await expect(missing).toHaveText("UNKNOWN");
    await expect(missing).not.toContainText("—");
    await expect(page.getByTestId("track-record-equity-card")).not.toContainText("—");

    await page.unroute("**/api/track-record/summary*");
    await page.unroute("**/api/track-record/closed*");
    await page.route("**/api/track-record/summary*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_closed: 1,
          wins: 1,
          losses: 0,
          hit_rate_pct: 100,
          avg_return_pct: 1,
          sharpe: 1,
          max_drawdown_pct: -1,
          cumulative_return_pct: 1,
          equity_curve: [],
          source: "   ",
        }),
      });
    });
    await page.route("**/api/track-record/closed*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          summary: { total_closed: 1, source: "\t" },
          records: [{ signal_id: "e2e-src-blank", asset: "BBB", outcome: "win", direction: "LONG" }],
          total: 1,
          limit: 50,
          offset: 0,
          source: "  ",
        }),
      });
    });
    await page.goto("/insights?tab=track-record", { waitUntil: "load" });
    const blank = page.getByTestId("track-record-equity-source");
    await expect(blank).toHaveText("UNKNOWN");
    await expect(blank).not.toContainText("—");
  });
});
