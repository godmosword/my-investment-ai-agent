// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Insights — first screen is 今日建議 (ITER-P4-44A)", () => {
  test("first screen is daily brief body, not workbench intro or portal CTAs", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const brief = page
      .locator(
        "[data-testid=daily-brief-panel], [data-testid=daily-brief-empty], [data-testid=daily-brief-loading], [data-testid=daily-brief-error]",
      )
      .first();
    await expect(brief).toBeVisible({ timeout: 60_000 });
    const briefBox = await brief.boundingBox();
    expect(briefBox).toBeTruthy();
    expect(briefBox.y).toBeGreaterThanOrEqual(0);
    expect(briefBox.y).toBeLessThan(720);

    await expect(page.getByTestId("portal-cta-insights-to-news")).toBeHidden();
    await expect(page.getByTestId("portal-cta-insights-to-columns")).toBeHidden();

    const health = page.getByTestId("insights-data-health-summary");
    const healthCollapsed = await health.evaluate((el) => {
      const details = el.closest("details");
      return Boolean(details && !details.open);
    });
    expect(healthCollapsed).toBe(true);

    await page.getByTestId("insights-intro-toggle").click();
    await expect(page.getByTestId("portal-cta-insights-to-news")).toBeVisible();
    await expect(page.getByTestId("portal-cta-insights-to-columns")).toBeVisible();
    await expect(page.getByTestId("insights-data-health-summary")).toBeVisible();
  });

  test("Terminal workspace is collapsed by default under 今日建議", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 720 });
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });

    const brief = page
      .locator(
        "[data-testid=daily-brief-panel], [data-testid=daily-brief-empty], [data-testid=daily-brief-loading], [data-testid=daily-brief-error]",
      )
      .first();
    await expect(brief).toBeVisible({ timeout: 60_000 });

    const note = page.getByTestId("daily-brief-workspace-note");
    await expect(note).toBeVisible();
    await expect(note).toContainText("不是今日建議");

    const workspace = page.getByTestId("daily-brief-workspace");
    await expect(workspace).toBeVisible();
    const workspaceCollapsed = await workspace.evaluate((el) => {
      return el instanceof HTMLDetailsElement && !el.open;
    });
    expect(workspaceCollapsed).toBe(true);

    const grid = page.getByTestId("terminal-workspace-grid");
    await expect(grid).toBeHidden();

    const briefBox = await brief.boundingBox();
    const workspaceBox = await workspace.boundingBox();
    expect(briefBox).toBeTruthy();
    expect(workspaceBox).toBeTruthy();
    expect(briefBox.y).toBeLessThan(workspaceBox.y);

    await page.getByTestId("daily-brief-workspace-toggle").click();
    await expect(grid).toBeVisible();
  });

  test("?tab=signals still opens QuantHome", async ({ page }) => {
    await page.goto("/insights?tab=signals", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("insights-tab-signals")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("quant-m7-signals")).toBeVisible({ timeout: 60_000 });
  });

  test("?symbol= still opens SymbolDeepDive", async ({ page }) => {
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("NVDA");
  });
});
