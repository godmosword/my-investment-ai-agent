// @ts-check
import { test, expect } from "@playwright/test";

test.describe("News route (/news)", () => {
  test("loads sourced digest, filters, and opens deep brief", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });

    await expect(page.getByTestId("news-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("AI 半導體供應鏈拉高資本支出")).toBeVisible();
    await expect(page.getByText("semianalysis.com")).toBeVisible();

    await page.getByTestId("news-filter-semis").click();
    await expect(page.getByText("AI 半導體供應鏈拉高資本支出")).toBeVisible();
    await expect(page.getByText("美元回落支撐科技股風險偏好")).toBeHidden();

    await page.getByTestId("news-digest-item").first().click();
    await expect(page.getByTestId("news-deep-panel")).toBeVisible();
    await expect(page.getByText("HBM 需求偏強")).toBeVisible();
    await expect(page.getByText("信心 82%")).toBeVisible();
  });
});
