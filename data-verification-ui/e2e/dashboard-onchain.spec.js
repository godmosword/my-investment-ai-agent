// @ts-check
import { test, expect } from "@playwright/test";

function isOnchainPath(pathname) {
  return pathname === "/api/macro/onchain" || pathname === "/api/macro/onchain/";
}

test.describe("Dashboard — Crypto on-chain mock panel (queue 45 · P5)", () => {
  test("not-live mock shows UNKNOWN header badge and UNKNOWN cells, not fake BTC dollars", async ({ page }) => {
    // 44b: onchain now lives under the 市場深度 tab.
    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("onchain-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("onchain-disclaimer")).toContainText("MOCK FIXTURE");
    const headerBadge = panel.getByTestId("onchain-source-badge");
    await expect(headerBadge).toHaveText(/unknown/i);
    await expect(headerBadge).not.toHaveText(/mock/i);
    await expect(
      page.getByTestId("onchain-btc-valuation").getByTestId("onchain-block-source-badge"),
    ).toHaveText(/mock/i);

    const valuation = page.getByTestId("onchain-btc-valuation");
    await expect(page.getByTestId("onchain-btc-valuation-empty")).toContainText("UNKNOWN：尚無真實資料");
    await expect(valuation).not.toContainText("MVRV-Z");
    await expect(valuation).not.toContainText("$38,500");

    const flow = page.getByTestId("onchain-exchange-flow");
    await expect(flow).toContainText("無免費同級來源");
    await expect(flow.getByText("All CEX", { exact: true })).toHaveCount(0);

    const funding = page.getByTestId("onchain-funding-rate");
    await expect(page.getByTestId("onchain-funding-rate-empty")).toContainText("UNKNOWN：尚無真實資料");
    await expect(funding).not.toContainText("6.8%");
  });

  test("not-live payload without source uses UNKNOWN, not mock", async ({ page }) => {
    await page.route(
      (url) => isOnchainPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            enabled: true,
            live: false,
            as_of: "2026-05-16",
            disclaimer: "e2e missing source — not a live feed",
            btc_valuation: { items: [] },
            exchange_flow: { enabled: false, source: "disabled", reason: "no_free_equivalent", items: [] },
            funding_rate: { items: [] },
          }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("onchain-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });

    const headerBadge = panel.getByTestId("onchain-source-badge");
    await expect(headerBadge).toHaveText(/unknown/i);
    await expect(headerBadge).not.toHaveText(/mock/i);

    const valuationBadge = page
      .getByTestId("onchain-btc-valuation")
      .getByTestId("onchain-block-source-badge");
    await expect(valuationBadge).toHaveText(/unknown/i);
    await expect(valuationBadge).not.toHaveText(/mock/i);
  });

  test("live header badge stays live", async ({ page }) => {
    await page.route(
      (url) => isOnchainPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            enabled: true,
            live: true,
            source: "binance_fapi",
            as_of: "2026-05-16",
            disclaimer: "LIVE e2e",
            btc_valuation: { source: "binance_fapi", items: [] },
            exchange_flow: { enabled: false, source: "disabled", reason: "no_free_equivalent", items: [] },
            funding_rate: { items: [] },
          }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("onchain-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel.getByTestId("onchain-source-badge")).toHaveText(/live/i);
  });

  test("present source string still shows when not live", async ({ page }) => {
    await page.route(
      (url) => isOnchainPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            enabled: true,
            live: false,
            source: "binance_fapi",
            as_of: "2026-05-16",
            disclaimer: "not live; named source",
            btc_valuation: { source: "binance_fapi", items: [] },
            exchange_flow: { enabled: false, source: "disabled", reason: "no_free_equivalent", items: [] },
            funding_rate: { items: [] },
          }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("onchain-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    const headerBadge = panel.getByTestId("onchain-source-badge");
    await expect(headerBadge).toHaveText(/binance_fapi/i);
    await expect(headerBadge).not.toHaveText(/mock/i);
    await expect(headerBadge).not.toHaveText(/unknown/i);
    await expect(
      page.getByTestId("onchain-btc-valuation").getByTestId("onchain-block-source-badge"),
    ).toHaveText(/binance_fapi/i);
  });
});
