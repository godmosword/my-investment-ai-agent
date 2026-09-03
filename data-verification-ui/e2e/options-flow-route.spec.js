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

    const flow = page.getByTestId("options-flow-table");
    await expect(flow).toBeVisible();
    await expect(flow.getByTestId("options-flow-row").first()).toBeVisible();
    // F3: localized signal label + parsed OCC contract (O:MU260116C00100000 → Call $100)
    await expect(flow.getByText("量/OI 異常", { exact: false }).first()).toBeVisible();
    await expect(flow.getByText("Call $100", { exact: false }).first()).toBeVisible();
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
});
