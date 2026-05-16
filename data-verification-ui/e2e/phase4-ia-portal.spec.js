// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Portal Phase 4 IA — reader layer × workbench cues (queue 44)", () => {
  test("reader layer intros + CTA hrefs", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("columns-reader-layer-intro")).toBeVisible();
    await expect(page.getByTestId("portal-cta-columns-to-insights")).toHaveAttribute("href", "/insights");

    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("insights-workbench-intro")).toBeVisible();
  });

  test("news CTA navigates to insights", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });
    await expect(page.getByTestId("news-reader-layer-intro")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("portal-cta-news-to-insights").click();
    await expect(page).toHaveURL(/\/insights/);
  });

  test("44c bidirectional CTAs — insights → news / columns", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-workbench-intro")).toBeVisible({ timeout: 60_000 });
    const newsCta = page.getByTestId("portal-cta-insights-to-news");
    const colCta = page.getByTestId("portal-cta-insights-to-columns");
    await expect(newsCta).toHaveAttribute("href", "/news");
    await expect(colCta).toHaveAttribute("href", "/columns");
    await newsCta.click();
    await expect(page).toHaveURL(/\/news/);
  });

  test("44c symbol deep-dive offers reverse CTAs with ?focus=", async ({ page }) => {
    await page.goto("/insights?symbol=AAPL", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-cta-to-news")).toHaveAttribute("href", "/news?focus=AAPL");
    await expect(page.getByTestId("symbol-cta-to-columns")).toHaveAttribute("href", "/columns?focus=AAPL");
    await page.getByTestId("symbol-cta-to-news").click();
    await expect(page).toHaveURL(/\/news\?focus=AAPL/);
    await expect(page.getByTestId("news-focus-badge")).toBeVisible();
  });

  test("44b dashboard splits to 宏觀/市場深度 tabs (compute-memory & onchain land under depth)", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    // overview is the default tab; depth content is hidden.
    await expect(page.getByTestId("dashboard-tab-overview")).toBeVisible();
    await expect(page.getByTestId("dashboard-tab-depth")).toBeVisible();
    await expect(page.getByTestId("macro-indicator-grid")).toBeVisible();
    await expect(page.getByTestId("compute-memory-panel")).toHaveCount(0);
    await expect(page.getByTestId("onchain-panel")).toHaveCount(0);

    // Switching to depth hides the macro grid and reveals the two dense panels.
    await page.getByTestId("dashboard-tab-depth").click();
    await expect(page).toHaveURL(/tab=depth/);
    await expect(page.getByTestId("macro-indicator-grid")).toHaveCount(0);
    await expect(page.getByTestId("compute-memory-panel")).toBeVisible();
    await expect(page.getByTestId("onchain-panel")).toBeVisible();
  });

  test("44b portfolio drops inline Watchlist (now lives in GlobalWatchlistDock only)", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    // Inline Watchlist (default testid `portfolio-watchlist`) removed; floating dock still site-wide.
    await expect(page.getByTestId("portfolio-watchlist")).toHaveCount(0);
    await expect(page.getByTestId("global-watchlist-toggle")).toBeVisible();
  });

  test("Command Bar placeholder softens on /news and stays terminal on /insights", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });
    const barNews = page.getByTestId("terminal-command-bar");
    await expect(barNews).toBeVisible({ timeout: 60_000 });
    await expect(barNews.getByPlaceholder(/搜尋主題焦點/i)).toBeVisible();

    await page.goto("/insights", { waitUntil: "load" });
    const barIn = page.getByTestId("terminal-command-bar");
    await expect(barIn).toBeVisible({ timeout: 60_000 });
    await expect(barIn.getByPlaceholder(/AAPL.*GO.*MACRO.*RUN/i)).toBeVisible();
  });
});
