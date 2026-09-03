// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights — Options Flow + GEX tab (F1)", () => {
  test("shows pending card when options backend is not configured", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("e2e_options_pending", "1");
    });
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-pending")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("options-pending")).toContainText("選擇權數據尚未上線");
  });

  test("separates missing API deployment from options data pending", async ({ page }) => {
    await page.route("**/api/options/summary*", async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not Found" }),
      });
    });

    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-api-missing")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("options-api-missing")).toContainText("API 尚未部署");
    await expect(page.getByTestId("options-pending")).toHaveCount(0);
  });

  test("watchlist strip shows GEX regime + unusual counts", async ({ page }) => {
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    const strip = page.getByTestId("options-watchlist");
    await expect(strip.locator('[data-symbol="MU"]')).toBeVisible();
    await expect(strip.locator('[data-symbol="NVDA"]')).toBeVisible();
    await expect(strip.getByText("MU", { exact: false })).toBeVisible();
    await expect(strip.locator('[data-symbol="AMD"]').getByTestId("options-watchlist-unusual")).toHaveText("0");
    await expect(strip.locator('[data-symbol="MU"]').getByTestId("options-watchlist-unusual")).toHaveText("2");
  });

  test("watchlist unusual_count null/omitted is UNKNOWN; real 0 stays 0", async ({ page }) => {
    await page.route("**/api/options/summary*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          as_of: "2026-06-19T22:30:00Z",
          watchlist: ["MU", "AMD", "INTC", "TSM"],
          items: [
            { underlying: "MU", gex: { total_gex: 300000, regime: "positive" }, unusual_count: 2 },
            { underlying: "AMD", gex: null, unusual_count: 0 },
            { underlying: "INTC", gex: { total_gex: 1000, regime: "positive" }, unusual_count: null },
            { underlying: "TSM", gex: { total_gex: 1000, regime: "positive" } },
          ],
        }),
      });
    });

    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    const chip = (sym) => page.locator(`[data-testid="options-watchlist-chip"][data-symbol="${sym}"]`);
    await expect(chip("MU").getByTestId("options-watchlist-unusual")).toHaveText("2");
    await expect(chip("AMD").getByTestId("options-watchlist-unusual")).toHaveText("0");
    await expect(chip("INTC").getByTestId("options-watchlist-unusual")).toHaveText("UNKNOWN");
    await expect(chip("TSM").getByTestId("options-watchlist-unusual")).toHaveText("UNKNOWN");
    await expect(chip("AMD").getByTestId("options-watchlist-unusual")).not.toHaveText("UNKNOWN");
  });

  test("selecting a symbol shows GEX panel + unusual flow rows", async ({ page }) => {
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    await page.locator('[data-testid="options-watchlist-chip"][data-symbol="MU"]').click();
    await expect(page.getByTestId("options-gex-panel")).toBeVisible();
    await expect(page.getByTestId("options-gex-panel").getByText("MU", { exact: true })).toBeVisible();
    await expect(page.getByTestId("options-gex-regime")).toHaveText("正 gamma（抑制波動）");

    const flow = page.getByTestId("options-flow-table");
    await expect(flow).toBeVisible();
    await expect(flow.getByTestId("options-flow-row").first()).toBeVisible();
    // F3: localized signal label + parsed OCC contract (O:MU260116C00100000 → Call $100)
    await expect(flow.getByText("量/OI 異常", { exact: false }).first()).toBeVisible();
    await expect(flow.getByText("Call $100", { exact: false }).first()).toBeVisible();
    await expect(flow.getByTestId("options-flow-row").first().getByTestId("options-score-bar")).toBeVisible();
    await expect(flow.getByTestId("options-flow-row").first().getByTestId("options-score-value")).toHaveText("0.50");
  });

  test("flow table renders mobile cards on small viewport (F3)", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 });
    await page.goto("/insights?tab=options&symbol=MU", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    const card = page.getByTestId("options-flow-card").first();
    await expect(card).toBeVisible();
    await expect(card.getByText("Call $100", { exact: false })).toBeVisible();
  });

  test("switching symbol updates the flow table contracts (F3)", async ({ page }) => {
    await page.goto("/insights?tab=options&symbol=MU", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("options-flow-table")).toContainText("Call $100");

    await page.locator('[data-testid="options-watchlist-chip"][data-symbol="NVDA"]').click();
    await expect(page).toHaveURL(/symbol=NVDA/);
    await expect(page.getByTestId("options-flow-table")).toContainText("Call $130");
  });

  test("GEX history chart renders when history is present (F2)", async ({ page }) => {
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    await page.locator('[data-testid="options-watchlist-chip"][data-symbol="MU"]').click();
    const chart = page.getByTestId("options-gex-chart");
    await expect(chart).toBeVisible();
    await expect(chart.locator("canvas").first()).toBeVisible();
  });

  test("symbol query param drives the URL on selection", async ({ page }) => {
    await page.goto("/insights?tab=options", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });

    await page.locator('[data-testid="options-watchlist-chip"][data-symbol="NVDA"]').click();
    await expect(page).toHaveURL(/symbol=NVDA/);
    await expect(page.getByTestId("options-gex-panel").getByText("NVDA", { exact: true })).toBeVisible();
  });

  test("ScoreBar missing score is UNKNOWN, not a 0.00 bar; finite 0 still draws", async ({ page }) => {
    await page.route("**/api/options/flow/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          underlying: "MU",
          as_of: "2026-06-19T22:30:00Z",
          signals: [
            {
              trade_date: "2026-06-19",
              option_ticker: "O:MU260116C00100000",
              signal_type: "volume_oi",
              score: 0,
              premium: 1000,
              volume: 10,
              open_interest: 20,
              rationale: "e2e finite zero score",
            },
            {
              trade_date: "2026-06-19",
              option_ticker: "O:MU260116C00110000",
              signal_type: "sweep",
              score: null,
              premium: 1000,
              volume: 10,
              open_interest: 20,
              rationale: "e2e missing score",
            },
            {
              trade_date: "2026-06-19",
              option_ticker: "O:MU260116C00120000",
              signal_type: "block",
              premium: 1000,
              volume: 10,
              open_interest: 20,
              rationale: "e2e omitted score",
            },
          ],
        }),
      });
    });

    await page.goto("/insights?tab=options&symbol=MU", { waitUntil: "load" });
    await expect(page.getByTestId("options-flow-home")).toBeVisible({ timeout: 60_000 });
    const rows = page.getByTestId("options-flow-row");
    await expect(rows).toHaveCount(3);

    await expect(rows.nth(0).getByTestId("options-score-bar")).toBeVisible();
    await expect(rows.nth(0).getByTestId("options-score-value")).toHaveText("0.00");
    await expect(rows.nth(0).getByTestId("options-score-unknown")).toHaveCount(0);

    await expect(rows.nth(1).getByTestId("options-score-unknown")).toHaveText("UNKNOWN");
    await expect(rows.nth(1).getByTestId("options-score-bar")).toHaveCount(0);
    await expect(rows.nth(1)).not.toContainText("0.00");

    await expect(rows.nth(2).getByTestId("options-score-unknown")).toHaveText("UNKNOWN");
    await expect(rows.nth(2).getByTestId("options-score-bar")).toHaveCount(0);
  });

  test("GexReadout missing regime is UNKNOWN and does not infer from total_gex sign", async ({ page }) => {
    await page.route("**/api/options/gex/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          underlying: "MU",
          as_of: "2026-06-19T22:30:00Z",
          gex: {
            underlying: "MU",
            total_gex: -450000,
            call_gex: 250000,
            put_gex: -700000,
            spot_price: 100,
            trade_date: "2026-06-19",
          },
          history: [],
          per_strike: [],
        }),
      });
    });

    await page.goto("/insights?tab=options&symbol=MU", { waitUntil: "load" });
    await expect(page.getByTestId("options-gex-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("options-gex-regime")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("options-gex-panel")).not.toContainText("正 gamma");
    await expect(page.getByTestId("options-gex-panel")).not.toContainText("負 gamma");
  });

  test("GexReadout shows 負 gamma only when regime is exactly negative", async ({ page }) => {
    await page.route("**/api/options/gex/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          underlying: "NVDA",
          as_of: "2026-06-19T22:30:00Z",
          gex: {
            underlying: "NVDA",
            total_gex: 300000,
            call_gex: 500000,
            put_gex: -200000,
            spot_price: 130,
            regime: "negative",
            trade_date: "2026-06-19",
          },
          history: [],
          per_strike: [],
        }),
      });
    });

    await page.goto("/insights?tab=options&symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("options-gex-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("options-gex-regime")).toHaveText("負 gamma（放大波動）");
    await expect(page.getByTestId("options-gex-regime")).not.toHaveText("UNKNOWN");
  });
});
