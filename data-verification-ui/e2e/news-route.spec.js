// @ts-check
import { test, expect } from "@playwright/test";

test.describe("News route (/news)", () => {
  test("loads sourced digest, filters, and opens deep brief", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });

    await expect(page.getByTestId("news-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("news-reader-layer-intro")).toBeVisible();
    await expect(page.getByTestId("portal-cta-news-to-insights")).toHaveAttribute("href", "/insights");

    await expect(page.getByText("AI 半導體供應鏈拉高資本支出")).toBeVisible();
    await expect(page.getByText("semianalysis.com")).toBeVisible();
    await expect(page.getByTestId("reader-source-line").first()).toContainText("過期");
    await expect(page.getByTestId("news-ai-interpretation").first()).toContainText("AI 解讀");
    await expect(page.getByTestId("news-ai-interpretation").first()).toContainText("雲端 capex");

    await page.getByTestId("news-filter-semis").click();
    await expect(page.getByText("AI 半導體供應鏈拉高資本支出")).toBeVisible();
    await expect(page.getByText("美元回落支撐科技股風險偏好")).toBeHidden();

    await page.getByTestId("news-digest-item").first().click();
    await expect(page.getByTestId("news-deep-panel")).toBeVisible();
    await expect(page.getByText("HBM 需求偏強")).toBeVisible();
    await expect(page.getByText("信心 82%")).toBeVisible();
    await expect(page.getByTestId("news-deep-panel").getByTestId("news-ai-interpretation")).toContainText("AI 解讀");
  });

  test("digest tickers only render from payload and skip cards without tickers", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });
    await expect(page.getByTestId("news-home")).toBeVisible({ timeout: 60_000 });

    const chipCard = page.locator("div.card").filter({ hasText: "AI 半導體供應鏈拉高資本支出" });
    await expect(chipCard.getByTestId("news-ticker-to-insights")).toHaveCount(2);
    await expect(chipCard.getByTestId("news-ticker-to-insights").nth(1)).toHaveAttribute("href", "/insights?symbol=TSM");

    const macroCard = page.locator("div.card").filter({ hasText: "美元回落支撐科技股風險偏好" });
    await expect(macroCard.getByTestId("news-ticker-to-insights")).toHaveCount(0);
  });

  test("ThemeRail click filters the list and empty uses existing copy", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });
    await expect(page.getByTestId("news-home")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("news-theme-chip").filter({ hasText: "半導體" }).click();
    await expect(page.getByText("AI 半導體供應鏈拉高資本支出")).toBeVisible();
    await expect(page.getByText("Bitcoin ETF 資金流回溫")).toBeHidden();
    await expect(page.getByText("美元回落支撐科技股風險偏好")).toBeHidden();

    await page.getByTestId("news-filter-crypto").click();
    await expect(page.getByText("尚無符合條件且具來源的新聞。")).toBeVisible();
  });

  test("missing gemini_take and freshness show UNKNOWN／未提供 and 未知", async ({ page }) => {
    await page.route("**/api/news/digest**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: "e2e-unknown-take",
              headline: "來源完整但無 AI 解讀",
              source_domain: "example.com",
              published_at: "2026-05-13T09:00:00Z",
              tags: ["AI"],
            },
          ],
          themes: [],
        }),
      });
    });
    await page.goto("/news", { waitUntil: "load" });
    await expect(page.getByTestId("news-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("news-ai-interpretation")).toContainText("AI 解讀");
    await expect(page.getByTestId("news-ai-interpretation")).toContainText("UNKNOWN／未提供");
    await expect(page.getByTestId("reader-source-line")).toContainText("未知");
    await expect(page.getByTestId("news-ticker-to-insights")).toHaveCount(0);
  });
});
