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
    await expect(page.getByTestId("earnings-insight-scaffold-badge")).toContainText("scaffold／非活 10-Q");
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
    await expect(page.getByTestId("earnings-cta-to-tech-pulse")).toHaveAttribute(
      "href",
      "https://tech-pulse.e2e.example/earnings/NVDA",
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

  test("calendar session status is 未知 and does not invent 盤前／盤後", async ({ page }) => {
    await page.goto("/insights?tab=earnings", { waitUntil: "load" });
    await expect(page.getByTestId("earnings-insight-home")).toBeVisible({ timeout: 60_000 });
    const statuses = page.getByTestId("earnings-session-status");
    await expect(statuses).toHaveCount(3);
    await expect(statuses.nth(0)).toHaveText("未知");
    await expect(statuses.nth(1)).toHaveText("未知");
    await expect(statuses.nth(2)).toHaveText("未知");
    const list = page.getByTestId("earnings-calendar-list");
    await expect(list).not.toContainText("盤前");
    await expect(list).not.toContainText("盤後");
  });

  test("empty insight states UNKNOWN beat/miss and guidance without fabricated numbers", async ({ page }) => {
    await page.goto("/insights?tab=earnings", { waitUntil: "load" });
    await expect(page.getByTestId("earnings-insight-home")).toBeVisible({ timeout: 60_000 });
    await page.locator('[data-testid="earnings-calendar-row"][data-symbol="TSM"]').click();
    const empty = page.getByTestId("earnings-insight-empty");
    await expect(empty).toBeVisible();
    await expect(page.getByTestId("earnings-insight-unknown")).toContainText("UNKNOWN：無共識 beat/miss、無 guidance");
    await expect(page.getByTestId("earnings-insight-detail")).toBeHidden();
    await expect(empty).not.toContainText("EPS");
  });

  test("enabled insight is labeled scaffold and empty citations are UNKNOWN", async ({ page }) => {
    await page.route("**/api/earnings/MSFT/insight", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          symbol: "MSFT",
          as_of: "2026-05-01",
          analysis: {
            ticker: "MSFT",
            filing_type: "10-Q",
            answers: { 1: "TEMPLATE" },
            citations: {},
            red_flags: [],
          },
        }),
      });
    });
    await page.goto("/insights?tab=earnings", { waitUntil: "load" });
    await expect(page.getByTestId("earnings-insight-home")).toBeVisible({ timeout: 60_000 });
    await page.locator('[data-testid="earnings-calendar-row"][data-symbol="MSFT"]').click();
    const detail = page.getByTestId("earnings-insight-detail");
    await expect(detail).toBeVisible();
    await expect(page.getByTestId("earnings-insight-scaffold-badge")).toContainText("scaffold／非活 10-Q");
    await expect(detail).toContainText("UNKNOWN");
    await expect(detail).not.toContainText("TEMPLATE");
    await expect(page.getByTestId("earnings-citation-unknown")).toContainText("UNKNOWN：無引用");
  });

});
