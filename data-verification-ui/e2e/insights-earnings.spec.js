// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights — Earnings calendar tab (P3)", () => {
  test("calendar lists upcoming tickers with pillar tags", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await page.getByTestId("insights-tab-earnings").click();
    await expect(page.getByTestId("earnings-insight-home")).toBeVisible({ timeout: 60_000 });

    const list = page.getByTestId("earnings-calendar-list");
    await expect(list.getByText("NVDA", { exact: true })).toBeVisible();
    await expect(list.getByText("MSFT", { exact: true })).toBeVisible();
    await expect(list.getByText("AI 矽晶")).toBeVisible();
    await expect(list.getByText("雲端／軟體")).toBeVisible();
  });

  test("clicking a ticker opens insight panel with scaffold + fusion CTAs", async ({ page }) => {
    await page.goto("/insights?tab=earnings", { waitUntil: "load" });
    await expect(page.getByTestId("earnings-insight-home")).toBeVisible({ timeout: 60_000 });

    const nvdaRow = page.locator('[data-testid="earnings-calendar-row"][data-symbol="NVDA"]');
    await nvdaRow.click();
    const panel = page.getByTestId("earnings-insight-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("earnings-insight-detail")).toBeVisible();
    await expect(panel.getByText("Datacenter revenue grew 80% YoY", { exact: false })).toBeVisible();
    await expect(panel.getByText("Inventory days up 12%")).toBeVisible();

    await expect(page.getByTestId("earnings-cta-to-deep-dive")).toHaveAttribute(
      "href",
      "/insights?symbol=NVDA",
    );
    await expect(page.getByTestId("earnings-cta-to-news")).toHaveAttribute("href", "/news?focus=NVDA");
    await expect(page.getByTestId("earnings-cta-to-columns")).toHaveAttribute(
      "href",
      "/columns?focus=NVDA",
    );
  });

  test("ticker without scaffold shows empty state, not fabricated numbers", async ({ page }) => {
    await page.goto("/insights?tab=earnings", { waitUntil: "load" });
    await expect(page.getByTestId("earnings-insight-home")).toBeVisible({ timeout: 60_000 });

    const tsmRow = page.locator('[data-testid="earnings-calendar-row"][data-symbol="TSM"]');
    await tsmRow.click();
    await expect(page.getByTestId("earnings-insight-empty")).toBeVisible();
    await expect(page.getByTestId("earnings-insight-detail")).toBeHidden();
  });
});
