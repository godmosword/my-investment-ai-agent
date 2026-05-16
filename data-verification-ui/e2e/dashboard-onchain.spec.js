// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Dashboard — Crypto on-chain mock panel (queue 45 · P5)", () => {
  test("renders three blocks with mock badge and disclaimer", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    const panel = page.getByTestId("onchain-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("onchain-disclaimer")).toContainText("MOCK FIXTURE");
    await expect(panel.getByTestId("onchain-source-badge").first()).toContainText(/mock/i);

    const valuation = page.getByTestId("onchain-btc-valuation");
    await expect(valuation.getByText("MVRV-Z", { exact: true })).toBeVisible();
    await expect(valuation.getByText("Realized Price", { exact: true })).toBeVisible();

    const flow = page.getByTestId("onchain-exchange-flow");
    await expect(flow.getByText("All CEX", { exact: true })).toBeVisible();
    await expect(flow.getByText("Binance", { exact: true })).toBeVisible();

    const funding = page.getByTestId("onchain-funding-rate");
    await expect(funding.getByText("BTC", { exact: true })).toBeVisible();
    await expect(funding.getByText("ETH", { exact: true })).toBeVisible();
  });
});
