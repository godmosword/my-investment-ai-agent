// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Dashboard — Crypto on-chain mock panel (queue 45 · P5)", () => {
  test("not-live mock shows badge and UNKNOWN, not fake BTC dollars", async ({ page }) => {
    // 44b: onchain now lives under the 市場深度 tab.
    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("onchain-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("onchain-disclaimer")).toContainText("MOCK FIXTURE");
    await expect(panel.getByTestId("onchain-source-badge").first()).toContainText(/mock/i);

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
});
