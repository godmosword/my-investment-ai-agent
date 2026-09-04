import { expect, test } from "@playwright/test";

test.describe("Insights symbol deep dive", () => {
  test("renders analysis bundle when symbol query param is present", async ({ page }) => {
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("NVDA");
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("$100.50");
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("e2e_mock");
  });

  test("shows paper QSREC marker for matching PAPER intent only", async ({ page }) => {
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("deep-dive-candle-chart")).toBeVisible();
    const markers = page.getByTestId("deep-dive-paper-markers");
    await expect(markers).toBeVisible();
    await expect(markers).toContainText("e2e-nvda-paper-1");
    await expect(markers).toContainText("2026-05-14");
    await expect(markers).not.toContainText("e2e-spy-1");
  });

  test("does not show paper markers for a symbol without PAPER intents", async ({ page }) => {
    await page.goto("/insights?symbol=BTC", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("deep-dive-paper-markers-empty")).toBeVisible();
    await expect(page.getByTestId("symbol-deep-dive")).not.toContainText("e2e-nvda-paper-1");
  });

  test("missing filing is UNKNOWN and latest_metrics are not shown as quarterly KPIs", async ({ page }) => {
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-filing-empty")).toBeVisible();
    await expect(page.getByTestId("symbol-filing-empty")).toContainText("尚無本股財報摘要");
    await expect(page.getByTestId("symbol-filing-empty")).toContainText("UNKNOWN");
    await expect(page.getByTestId("symbol-filing-block")).toHaveCount(0);
    const diveRoot = page.getByTestId("symbol-deep-dive");
    await expect(diveRoot).not.toContainText("mvrv_z_score");
    await expect(diveRoot).not.toContainText("sopr");
    await expect(diveRoot).not.toContainText("etf_flow_millions");
  });

  test("missing source/as_of and non-finite last price are UNKNOWN, not em dash", async ({ page }) => {
    await page.route(
      (url) => url.pathname === "/api/analysis/NVDA" || url.pathname === "/api/analysis/NVDA/",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            symbol: "NVDA",
            quote: { symbol: "NVDA", last: null },
            snapshot: { symbol: "NVDA", source: "", as_of: "", price_series: [] },
            snapshot_error: null,
          }),
        });
      },
    );
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-last-price")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("symbol-snapshot-source")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("symbol-snapshot-as-of")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("symbol-last-price")).not.toHaveText("—");
    await expect(page.getByTestId("symbol-snapshot-source")).not.toHaveText("—");
    await expect(page.getByTestId("symbol-snapshot-as-of")).not.toHaveText("—");
    await expect(page.getByTestId("symbol-deep-dive")).not.toContainText("—");
  });

  test("finite last price 0 stays $0.00; present source and as_of still render", async ({ page }) => {
    await page.route(
      (url) => url.pathname === "/api/analysis/NVDA" || url.pathname === "/api/analysis/NVDA/",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            symbol: "NVDA",
            quote: { symbol: "NVDA", last: 0, as_of: "2026-05-14T00:00:00Z" },
            snapshot: { symbol: "NVDA", source: "e2e_zero", as_of: "2026-05-14T00:00:00Z", price_series: [] },
            snapshot_error: null,
          }),
        });
      },
    );
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-last-price")).toHaveText("$0.00");
    await expect(page.getByTestId("symbol-last-price")).not.toHaveText("UNKNOWN");
    await expect(page.getByTestId("symbol-snapshot-source")).toHaveText("e2e_zero");
    await expect(page.getByTestId("symbol-snapshot-as-of")).toHaveText("2026-05-14T00:00:00Z");
  });
});
