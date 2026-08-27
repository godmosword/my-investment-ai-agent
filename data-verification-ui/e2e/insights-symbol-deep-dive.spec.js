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
});
