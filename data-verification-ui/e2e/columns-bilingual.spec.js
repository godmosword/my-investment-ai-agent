// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Columns — bilingual commentary (queue 45 · P4)", () => {
  test("shows zh/en toggle when both commentary fields exist", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });

    // Pillar "semiconductor" includes the e2e-ai-chip mock item which has both
    // commentary_zh and commentary_en.
    await page.getByTestId("columns-pillar-semiconductor").click();
    const card = page.getByTestId("columns-deep-card").first();
    await expect(card).toBeVisible({ timeout: 15_000 });
    await expect(card.getByTestId("reader-source-line")).toContainText("過期");
    await expect(card.getByTestId("columns-ai-interpretation")).toContainText("AI 解讀");
    await expect(card.getByTestId("columns-ai-interpretation")).toContainText("雲端 capex");
    await expect(card.getByTestId("columns-ai-interpretation")).toContainText("HBM");
    await card.click();

    const panel = page.getByTestId("columns-deep-panel");
    await expect(panel).toBeVisible();
    await expect(panel.getByTestId("columns-ai-interpretation")).toContainText("AI 解讀");
    await expect(panel.getByTestId("columns-ai-interpretation")).toContainText("雲端 capex");

    const toggle = page.getByTestId("columns-commentary-toggle");
    await expect(toggle).toBeVisible();
    const commentary = page.getByTestId("columns-commentary-text");
    await expect(commentary).toContainText("HBM");

    await page.getByTestId("columns-commentary-en").click();
    await expect(commentary).toContainText(/Supply chain/i);
    await page.getByTestId("columns-commentary-zh").click();
    await expect(commentary).toContainText("供應鏈");
  });

  test("missing gemini_take shows UNKNOWN／未提供", async ({ page }) => {
    await page.route("**/api/news/deep**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          pillar: "ai",
          items: [
            {
              id: "e2e-unknown-take",
              title: "來源完整但無 AI 解讀",
              source_domain: "example.com",
              published_at: "2026-05-13T09:00:00Z",
              body: "正文來自來源，沒有 gemini_take。",
              deep_brief: "正文來自來源，沒有 gemini_take。",
            },
          ],
        }),
      });
    });
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("columns-ai-interpretation")).toContainText("AI 解讀");
    await expect(page.getByTestId("columns-ai-interpretation")).toContainText("UNKNOWN／未提供");
    await expect(page.getByText("摘要待補。")).toHaveCount(0);
  });

  test("RelatedThemes payload symbols link to insights", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    const nvda = page.getByTestId("columns-theme-symbol-to-insights").filter({ hasText: "NVDA" }).first();
    await expect(nvda).toHaveAttribute("href", "/insights?symbol=NVDA");
  });

  test("desktop deep panel stays in viewport next to an early digest card", async ({ page }) => {
    const viewport = { width: 1280, height: 800 };
    await page.setViewportSize(viewport);
    await page.route("**/api/news/deep**", async (route) => {
      const items = Array.from({ length: 12 }, (_, index) => ({
        id: `e2e-desktop-adj-${index}`,
        title: index === 0 ? "第一則 Deep Brief 卡片" : `Deep Brief 卡片 ${index + 1}`,
        headline: index === 0 ? "第一則 Deep Brief 卡片" : `Deep Brief 卡片 ${index + 1}`,
        source_domain: "example.com",
        published_at: "2026-05-13T09:00:00Z",
        gemini_take: "UNKNOWN／未提供",
        deep_brief: "正文來自來源。",
        body: "正文來自來源。",
      }));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ pillar: "ai", items }),
      });
    });
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("columns-deep-card").first().click();
    const panel = page.getByTestId("columns-deep-panel");
    await expect(panel).toBeVisible();
    const box = await panel.boundingBox();
    expect(box).toBeTruthy();
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect(box.y).toBeLessThan(viewport.height);
  });
});
