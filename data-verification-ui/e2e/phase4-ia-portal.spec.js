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
