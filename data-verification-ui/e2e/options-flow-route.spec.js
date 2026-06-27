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
