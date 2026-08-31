// @ts-check
import { test, expect } from "@playwright/test";

const VIEWPORT = { width: 390, height: 720 };

/** @param {import("@playwright/test").Locator} locator */
async function expectInViewport(locator) {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).toBeTruthy();
  expect(box.y + box.height).toBeGreaterThan(0);
  expect(box.y).toBeLessThan(VIEWPORT.height);
  expect(box.x + box.width).toBeGreaterThan(0);
  expect(box.x).toBeLessThan(VIEWPORT.width);
}

test.describe("Columns — Deep Brief card hit (ITER-P4-44A)", () => {
  test("clicking columns-deep-card shows full article in 390×720 viewport", async ({ page }) => {
    await page.setViewportSize(VIEWPORT);
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });

    const card = page.getByTestId("columns-deep-card").first();
    await expect(card).toBeVisible({ timeout: 15_000 });
    await card.click();

    await expect(page).toHaveURL(/\/columns/);
    const panel = page.getByTestId("columns-deep-panel");
    await expect(panel).toBeVisible();
    await expectInViewport(panel);

    const title = panel.getByRole("heading", { name: "AI 半導體供應鏈拉高資本支出" });
    const source = panel.getByTestId("reader-source-line");
    const body = panel.getByText("對 NVDA/TSM 的訂單能見度形成支撐");
    await expect(title).toBeVisible();
    await expect(source).toContainText("semianalysis.com");
    await expect(body).toBeVisible();
    await expectInViewport(title);
    await expectInViewport(source);
    await expectInViewport(body);
  });

  test("loading copy stays honest", async ({ page }) => {
    await page.route("**/api/news/deep**", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 8_000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ pillar: "ai", items: [] }),
      });
    });
    await page.setViewportSize(VIEWPORT);
    await page.goto("/columns", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("載入 Deep Brief…")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId("columns-deep-card")).toHaveCount(0);
    await expect(page.getByTestId("columns-deep-panel")).toHaveCount(0);
  });

  test("empty pillar stays honest", async ({ page }) => {
    await page.route("**/api/news/deep**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ pillar: "ai", items: [] }),
      });
    });
    await page.setViewportSize(VIEWPORT);
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("此支柱暫無具來源的 Deep Brief。")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("columns-deep-card")).toHaveCount(0);
    await expect(page.getByTestId("columns-deep-panel")).toHaveCount(0);
    await expect(page.getByText("AI 半導體供應鏈拉高資本支出")).toHaveCount(0);
  });

  test("error copy stays honest", async ({ page }) => {
    await page.route("**/api/news/deep**", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "e2e deep list fail" }),
      });
    });
    await page.setViewportSize(VIEWPORT);
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Deep Brief 暫時無法載入。")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("columns-deep-card")).toHaveCount(0);
    await expect(page.getByTestId("columns-deep-panel")).toHaveCount(0);
    await expect(page.getByText("AI 半導體供應鏈拉高資本支出")).toHaveCount(0);
  });
});
