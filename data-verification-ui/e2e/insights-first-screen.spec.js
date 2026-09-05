// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights — first screen is 今日建議 (ITER-P4-44A)", () => {
  test("first screen is daily brief body, not workbench intro or portal CTAs", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const brief = page
      .locator(
        "[data-testid=daily-brief-panel], [data-testid=daily-brief-empty], [data-testid=daily-brief-loading], [data-testid=daily-brief-error]",
      )
      .first();
    await expect(brief).toBeVisible({ timeout: 60_000 });
    const briefBox = await brief.boundingBox();
    expect(briefBox).toBeTruthy();
    expect(briefBox.y).toBeGreaterThanOrEqual(0);
    expect(briefBox.y).toBeLessThan(720);

    await expect(page.getByTestId("portal-cta-insights-to-news")).toBeHidden();
    await expect(page.getByTestId("portal-cta-insights-to-columns")).toBeHidden();

    const health = page.getByTestId("insights-data-health-summary");
    const healthCollapsed = await health.evaluate((el) => {
      const details = el.closest("details");
      return Boolean(details && !details.open);
    });
    expect(healthCollapsed).toBe(true);

    await page.getByTestId("insights-intro-toggle").click();
    await expect(page.getByTestId("portal-cta-insights-to-news")).toBeVisible();
    await expect(page.getByTestId("portal-cta-insights-to-columns")).toBeVisible();
    await expect(page.getByTestId("insights-data-health-summary")).toBeVisible();
  });

  test("Terminal workspace is collapsed by default under 今日建議", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const brief = page
      .locator(
        "[data-testid=daily-brief-panel], [data-testid=daily-brief-empty], [data-testid=daily-brief-loading], [data-testid=daily-brief-error]",
      )
      .first();
    await expect(brief).toBeVisible({ timeout: 60_000 });

    const note = page.getByTestId("daily-brief-workspace-note");
    await expect(note).toBeVisible();
    await expect(note).toContainText("不是今日建議");

    const workspace = page.getByTestId("daily-brief-workspace");
    await expect(workspace).toBeVisible();
    const workspaceCollapsed = await workspace.evaluate((el) => {
      return el instanceof HTMLDetailsElement && !el.open;
    });
    expect(workspaceCollapsed).toBe(true);

    const grid = page.getByTestId("terminal-workspace-grid");
    await expect(grid).toBeHidden();

    const briefBox = await brief.boundingBox();
    const workspaceBox = await workspace.boundingBox();
    expect(briefBox).toBeTruthy();
    expect(workspaceBox).toBeTruthy();
    expect(briefBox.y).toBeLessThan(workspaceBox.y);

    await page.getByTestId("daily-brief-workspace-toggle").click();
    await expect(grid).toBeVisible();
  });

  test("news/columns toggle sits after 今日建議 and before Terminal", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const brief = page
      .locator(
        "[data-testid=daily-brief-panel], [data-testid=daily-brief-empty], [data-testid=daily-brief-loading], [data-testid=daily-brief-error]",
      )
      .first();
    await expect(brief).toBeVisible({ timeout: 60_000 });

    const intro = page.getByTestId("insights-workbench-intro");
    const workspace = page.getByTestId("daily-brief-workspace");
    await expect(intro).toBeVisible();
    await expect(workspace).toBeVisible();

    const briefBox = await brief.boundingBox();
    const introBox = await intro.boundingBox();
    const workspaceBox = await workspace.boundingBox();
    expect(briefBox).toBeTruthy();
    expect(introBox).toBeTruthy();
    expect(workspaceBox).toBeTruthy();
    expect(briefBox.y).toBeLessThan(introBox.y);
    expect(introBox.y).toBeLessThan(workspaceBox.y);
    expect(introBox.y).toBeLessThan(720);

    const introCollapsed = await intro.evaluate((el) => {
      return el instanceof HTMLDetailsElement && !el.open;
    });
    expect(introCollapsed).toBe(true);
    await expect(page.getByTestId("portal-cta-insights-to-news")).toBeHidden();
    await expect(page.getByTestId("portal-cta-insights-to-columns")).toBeHidden();
    await expect(page.getByTestId("portal-cta-insights-to-news")).toHaveCount(1);
    await expect(page.getByTestId("portal-cta-insights-to-columns")).toHaveCount(1);

    await page.getByTestId("insights-intro-toggle").click();
    await expect(page.getByTestId("portal-cta-insights-to-news")).toBeVisible();
    await expect(page.getByTestId("portal-cta-insights-to-columns")).toBeVisible();

    const briefAfter = await brief.boundingBox();
    const introAfter = await intro.boundingBox();
    expect(briefAfter.y).toBeLessThan(introAfter.y);
  });

  test("data health labels are zh; missing source/row_count is 檢查中", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("insights-intro-toggle").click();

    const health = page.getByTestId("insights-data-health-summary");
    await expect(health).toBeVisible();
    await expect(health.getByTestId("insights-health-label")).toHaveText(["日報", "紙上", "實績", "情境", "選擇權"]);

    await page.route("**/api/data-health*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          items: [
            { id: "reports", status: "ready" },
            { id: "paper", status: "ready", row_count: 1, source: "e2e" },
            { id: "track-record", status: "ready", row_count: 1, source: "e2e" },
            { id: "scenario", status: "ready", row_count: 1, source: "e2e" },
            { id: "options", status: "pending" },
          ],
        }),
      });
    });
    await page.reload({ waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("insights-intro-toggle").click();
    await expect(page.getByTestId("insights-health-reports").getByTestId("insights-health-meta")).toHaveText("檢查中");
    await expect(page.getByTestId("insights-health-options").getByTestId("insights-health-meta")).toHaveText("檢查中");
    await expect(page.getByTestId("insights-health-paper").getByTestId("insights-health-meta")).toHaveText("1 筆");
    await expect(page.getByTestId("insights-health-track-record").getByTestId("insights-health-meta")).toHaveText(
      "1 筆",
    );
    await expect(page.getByTestId("insights-health-scenario").getByTestId("insights-health-meta")).toHaveText("1 筆");
    await expect(page.getByTestId("insights-data-health-summary")).not.toContainText("checking");
    await expect(page.getByTestId("insights-data-health-summary")).not.toContainText("rows");
  });

  test("data health status chips are zh, not English codes", async ({ page }) => {
    const statusOf = (id) => page.getByTestId(`insights-health-${id}`).getByTestId("insights-health-status");

    await page.route("**/api/data-health*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          items: [
            { id: "reports", status: "ready", row_count: 1, source: "e2e" },
            { id: "paper", status: "empty", row_count: 0, source: "e2e" },
            { id: "track-record", status: "stale", row_count: 1, source: "e2e" },
            { id: "scenario", status: "error", row_count: 1, source: "e2e" },
            { id: "options", status: "loading" },
          ],
        }),
      });
    });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("insights-intro-toggle").click();

    await expect(statusOf("reports")).toHaveText("就緒");
    await expect(statusOf("paper")).toHaveText("空");
    await expect(statusOf("track-record")).toHaveText("過期");
    await expect(statusOf("scenario")).toHaveText("錯誤");
    await expect(statusOf("options")).toHaveText("載入中");

    const health = page.getByTestId("insights-data-health-summary");
    await expect(health).not.toContainText("ready");
    await expect(health).not.toContainText("empty");
    await expect(health).not.toContainText("stale");
    await expect(health).not.toContainText("error");
    await expect(health).not.toContainText("loading");

    await page.route("**/api/data-health*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          items: [
            { id: "reports", status: "pending" },
            { id: "paper", status: "mystery" },
            { id: "track-record", status: "ready", row_count: 1, source: "e2e" },
            { id: "scenario", status: "ready", row_count: 1, source: "e2e" },
            { id: "options", status: "ready", row_count: 1, source: "e2e" },
          ],
        }),
      });
    });
    await page.reload({ waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("insights-intro-toggle").click();
    await expect(statusOf("reports")).toHaveText("等待中");
    await expect(statusOf("paper")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("insights-data-health-summary")).not.toContainText("pending");
  });

  test("?tab=signals still opens QuantHome", async ({ page }) => {
    await page.goto("/insights?tab=signals", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("insights-tab-signals")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("quant-m7-signals")).toBeVisible({ timeout: 60_000 });
  });

  test("?symbol= still opens SymbolDeepDive", async ({ page }) => {
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("NVDA");
  });
});

function isReportDetailPath(pathname) {
  return /^\/api\/reports\/\d{4}-\d{2}-\d{2}$/.test(pathname);
}

function isPaperLifecyclePath(pathname) {
  return pathname === "/api/paper/lifecycle" || pathname === "/api/paper/pnl";
}

function isTrackRecordClosedPath(pathname) {
  return pathname === "/api/track-record/closed";
}

function isExecutionIntentsListPath(pathname) {
  return pathname === "/api/execution-intents";
}

function briefReport(symbols) {
  return {
    report_date: "2026-05-09",
    timestamp: "2026-04-14T00:00:00Z",
    grok_summary: "e2e grok",
    gpt_summary: "e2e gpt",
    tickers: symbols,
    recommendations: symbols.map((asset) => ({ asset })),
  };
}

function lifecyclePayload(rows) {
  return {
    as_of: "2026-05-13T00:00:00Z",
    source: "e2e",
    summary: { total: rows.length, active_count: 0, closed_count: 0 },
    rows,
  };
}

function closedPayload(records) {
  return {
    summary: { total_closed: records.length },
    records,
    total: records.length,
    limit: 50,
    offset: 0,
    source: "e2e",
  };
}

async function fulfillJson(route, body, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.describe("Insights — 紙上對帳 on first screen (ITER-TR-LOOP-001)", () => {
  test("first screen shows 紙上對帳 without opening 實績 tab", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const strip = page.getByTestId("paper-reconcile-strip");
    await expect(strip).toBeVisible({ timeout: 60_000 });
    await expect(strip).toContainText("紙上對帳");
    await expect(page.getByTestId("paper-reconcile-empty")).toBeVisible();
    await expect(page.getByTestId("paper-reconcile-empty")).toContainText("UNKNOWN：日報未提供已解析標的");
    await expect(page.getByTestId("paper-reconcile-row")).toHaveCount(0);
    await expect(strip).not.toContainText("—");
    await expect(strip).not.toContainText("$0");
    await expect(page.getByTestId("track-record-home")).toHaveCount(0);
    await expect(page.getByTestId("paper-lifecycle-home")).toHaveCount(0);

    const brief = page.getByTestId("daily-brief-panel");
    const stripBox = await strip.boundingBox();
    const briefBox = await brief.boundingBox();
    expect(stripBox).toBeTruthy();
    expect(briefBox).toBeTruthy();
    expect(briefBox.y).toBeLessThan(stripBox.y);
    expect(stripBox.y).toBeLessThan(720);
  });

  test("open / closed+return / no paper row use designed vocabulary", async ({ page }) => {
    await page.route((url) => isReportDetailPath(url.pathname), async (route) => {
      await fulfillJson(route, briefReport(["NVDA", "BTC", "AAPL"]));
    });
    await page.route((url) => isPaperLifecyclePath(url.pathname), async (route) => {
      await fulfillJson(
        route,
        lifecyclePayload([
          { asset: "NVDA", status: "APPROVED_FOR_PAPER", return_pct: 12 },
        ]),
      );
    });
    await page.route((url) => isTrackRecordClosedPath(url.pathname), async (route) => {
      await fulfillJson(
        route,
        closedPayload([
          { asset: "BTC", status: "PAPER_CLOSED", return_pct: 10, signal_id: "e2e-btc-closed" },
        ]),
      );
    });
    await page.route((url) => isExecutionIntentsListPath(url.pathname), async (route) => {
      await fulfillJson(route, []);
    });

    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("paper-reconcile-strip")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("paper-reconcile-rows")).toBeVisible();
    await expect(page.getByTestId("track-record-home")).toHaveCount(0);

    const nvda = page.locator("[data-testid=paper-reconcile-row][data-symbol=NVDA]");
    const btc = page.locator("[data-testid=paper-reconcile-row][data-symbol=BTC]");
    const aapl = page.locator("[data-testid=paper-reconcile-row][data-symbol=AAPL]");
    await expect(nvda).toBeVisible();
    await expect(nvda).toHaveAttribute("data-status", "open");
    await expect(nvda.getByTestId("paper-reconcile-open")).toHaveText("紙上未結");
    await expect(btc).toHaveAttribute("data-status", "closed");
    await expect(btc.getByTestId("paper-reconcile-closed")).toHaveText("紙上已結");
    await expect(btc.getByTestId("paper-reconcile-return")).toHaveText("10");
    await expect(aapl).toHaveAttribute("data-status", "none");
    await expect(aapl.getByTestId("paper-reconcile-none")).toHaveText("無紙上記錄");

    const strip = page.getByTestId("paper-reconcile-strip");
    await expect(strip).not.toContainText("—");
    await expect(strip).not.toContainText("$0");
    await expect(strip).not.toContainText("紙上已結 $");
  });

  test("closed finite 0 stays 0; missing return is UNKNOWN", async ({ page }) => {
    await page.route((url) => isReportDetailPath(url.pathname), async (route) => {
      await fulfillJson(route, briefReport(["MSFT", "TSLA"]));
    });
    await page.route((url) => isPaperLifecyclePath(url.pathname), async (route) => {
      await fulfillJson(route, lifecyclePayload([]));
    });
    await page.route((url) => isTrackRecordClosedPath(url.pathname), async (route) => {
      await fulfillJson(
        route,
        closedPayload([
          { asset: "MSFT", status: "PAPER_CLOSED", return_pct: 0, signal_id: "e2e-msft-flat" },
          { asset: "TSLA", status: "PAPER_CLOSED", signal_id: "e2e-tsla-missing" },
        ]),
      );
    });
    await page.route((url) => isExecutionIntentsListPath(url.pathname), async (route) => {
      await fulfillJson(route, []);
    });

    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("paper-reconcile-rows")).toBeVisible({ timeout: 60_000 });

    const msft = page.locator("[data-testid=paper-reconcile-row][data-symbol=MSFT]");
    const tsla = page.locator("[data-testid=paper-reconcile-row][data-symbol=TSLA]");
    await expect(msft).toHaveAttribute("data-status", "closed");
    await expect(msft.getByTestId("paper-reconcile-return")).toHaveText("0");
    await expect(tsla).toHaveAttribute("data-status", "unknown");
    await expect(tsla.getByTestId("paper-reconcile-missing-field")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("paper-reconcile-strip")).not.toContainText("—");
    await expect(page.getByTestId("paper-reconcile-strip")).not.toContainText("$0");
  });

  test("stale APPROVED_FOR_PAPER on track-record closed does not override PAPER_CLOSED", async ({
    page,
  }) => {
    await page.route((url) => isReportDetailPath(url.pathname), async (route) => {
      await fulfillJson(route, briefReport(["NVDA"]));
    });
    await page.route((url) => isPaperLifecyclePath(url.pathname), async (route) => {
      await fulfillJson(
        route,
        lifecyclePayload([
          { asset: "NVDA", status: "PAPER_CLOSED", return_pct: 8, signal_id: "e2e-nvda-closed" },
        ]),
      );
    });
    await page.route((url) => isTrackRecordClosedPath(url.pathname), async (route) => {
      await fulfillJson(
        route,
        closedPayload([
          {
            asset: "NVDA",
            status: "APPROVED_FOR_PAPER",
            return_pct: 12,
            signal_id: "e2e-nvda-closed",
            closed_at: "2026-05-11T00:00:00Z",
          },
          {
            asset: "NVDA",
            status: "PAPER_CLOSED",
            return_pct: 8,
            signal_id: "e2e-nvda-closed",
            closed_at: "2026-05-13T00:00:00Z",
          },
        ]),
      );
    });
    await page.route((url) => isExecutionIntentsListPath(url.pathname), async (route) => {
      await fulfillJson(route, [
        { asset: "NVDA", status: "APPROVED_FOR_PAPER", signal_id: "e2e-nvda-closed" },
      ]);
    });

    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("paper-reconcile-rows")).toBeVisible({ timeout: 60_000 });

    const nvda = page.locator("[data-testid=paper-reconcile-row][data-symbol=NVDA]");
    await expect(nvda).toHaveAttribute("data-status", "closed");
    await expect(nvda.getByTestId("paper-reconcile-closed")).toHaveText("紙上已結");
    await expect(nvda.getByTestId("paper-reconcile-return")).toHaveText("8");
    await expect(nvda.getByTestId("paper-reconcile-open")).toHaveCount(0);
    await expect(page.getByTestId("paper-reconcile-strip")).not.toContainText("紙上未結");
  });

  test("paper API 500 is error, distinct from empty", async ({ page }) => {
    await page.route((url) => isReportDetailPath(url.pathname), async (route) => {
      await fulfillJson(route, briefReport(["NVDA"]));
    });
    await page.route((url) => isPaperLifecyclePath(url.pathname), async (route) => {
      await fulfillJson(route, { detail: "e2e paper fail" }, 500);
    });

    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("paper-reconcile-error")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("paper-reconcile-empty")).toHaveCount(0);
    await expect(page.getByTestId("paper-reconcile-rows")).toHaveCount(0);
  });

  test("實績 and 生命週期 links stay on /insights tabs", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("paper-reconcile-strip")).toBeVisible({ timeout: 60_000 });

    const trackLink = page.getByTestId("paper-reconcile-link-track-record");
    const paperLink = page.getByTestId("paper-reconcile-link-paper");
    await expect(trackLink).toHaveAttribute("href", "/insights?tab=track-record");
    await expect(paperLink).toHaveAttribute("href", "/insights?tab=paper");
    await expect(trackLink).not.toHaveAttribute("target", "_blank");
    await expect(paperLink).not.toHaveAttribute("target", "_blank");

    await trackLink.click();
    await expect(page).toHaveURL(/\/insights\?tab=track-record/);
    await expect(page.getByTestId("insights-tab-track-record")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("track-record-home")).toBeVisible({ timeout: 60_000 });

    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("paper-reconcile-link-paper")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("paper-reconcile-link-paper").click();
    await expect(page).toHaveURL(/\/insights\?tab=paper/);
    await expect(page.getByTestId("insights-tab-paper")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
  });
});
