// @ts-check
import { test, expect } from "@playwright/test";

function isQuantSignalsPath(pathname) {
  return pathname === "/api/quant/signals" || pathname === "/api/quant/signals/";
}

/** Exact empty-store payload from GET /api/quant/signals (api.list_quant_signals_m7). */
const PLACEHOLDER_PAYLOAD = {
  disclaimer: "Paper / educational only; no performance guarantee; not investment advice.",
  source: "placeholder",
  count: 1,
  signals: [
    {
      id: "placeholder-neutral",
      symbol: "",
      label: "RSI14 neutral band (example)",
      direction: "neutral",
      confidence: 0.0,
    },
  ],
};

test.describe("Insights — 訊號 honesty (ITER-V2-012)", () => {
  test("placeholder RSI14 is not shown as a real signal", async ({ page }) => {
    await page.route(
      (url) => isQuantSignalsPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(PLACEHOLDER_PAYLOAD),
        });
      },
    );

    await page.goto("/insights?tab=signals", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const card = page.getByTestId("quant-m7-signals");
    await expect(card).toBeVisible({ timeout: 60_000 });
    const empty = page.getByTestId("quant-m7-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("UNKNOWN：尚無真實訊號");
    await expect(card).not.toContainText("RSI14");
    await expect(card).not.toContainText("RSI");
    await expect(page.getByTestId("quant-m7-error")).toHaveCount(0);
    await expect(page.getByTestId("quant-m7-list")).toHaveCount(0);
    await expect(page.getByTestId("quant-intraday-monitor")).not.toContainText("RSI14");
  });

  test("default mock paper signals still render labels", async ({ page }) => {
    await page.goto("/insights?tab=signals", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const card = page.getByTestId("quant-m7-signals");
    await expect(card).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("quant-m7-list")).toBeVisible();
    await expect(card).toContainText("AI capex momentum");
    await expect(card).toContainText("Index hedge watch");
    await expect(page.getByTestId("quant-m7-empty")).toHaveCount(0);
    await expect(page.getByTestId("quant-m7-error")).toHaveCount(0);
  });

  test("signals 500 shows error, not empty or RSI", async ({ page }) => {
    await page.route(
      (url) => isQuantSignalsPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "e2e signals fail" }),
        });
      },
    );

    await page.goto("/insights?tab=signals", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const err = page.getByTestId("quant-m7-error");
    await expect(err).toBeVisible({ timeout: 60_000 });
    await expect(err).toContainText("無法載入訊號");
    await expect(page.getByTestId("quant-m7-empty")).toHaveCount(0);
    await expect(page.getByTestId("quant-m7-list")).toHaveCount(0);
    await expect(page.getByTestId("quant-m7-signals")).not.toContainText("RSI14");
  });
});
