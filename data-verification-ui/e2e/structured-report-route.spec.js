// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Structured report route (VITE_STRUCTURED_REPORT)", () => {
  test("loads block view from GET /api/reports/{date}/structured", async ({ page }) => {
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/每日投資戰報 · 區塊視圖/)).toBeVisible();
    await expect(page.locator(".page-title").filter({ hasText: "2026-04-14" })).toBeVisible();
    await expect(page.getByText(/結構化本文尚未入庫/)).not.toBeVisible();
    await expect(page.getByText("e2e structured thesis").first()).toBeVisible();
    await expect(page.getByText("e2e structured bullet")).toBeVisible();
    await expect(page.getByText(/風險偏好（risk_on）/)).toBeVisible();
    await expect(page.getByText("e2e narrative of day")).toBeVisible();
    await expect(page.getByText("e2e scorecard line A")).toBeVisible();
    await expect(page.locator('section[data-section="exec_summary"]')).toBeVisible();
    await expect(page.locator('section[data-section="crypto_dashboard"]')).toBeVisible();
    await expect(page.getByTestId("current-affairs-roundtable-topic")).toHaveText("e2e roundtable topic");
    // full profile：crypto_dashboard 無 DBR 列時仍走 legacy grok 摘要
    await expect(page.getByText("e2e grok").first()).toBeVisible();
  });

  test("profile=lite shows lite in subtitle", async ({ page }) => {
    await page.goto("/report/2026-04-14?profile=lite", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/區塊視圖（lite）/)).toBeVisible();
    await expect(page.getByText(/結構化本文尚未入庫/)).not.toBeVisible();
    await expect(page.getByText("e2e structured thesis").first()).toBeVisible();
  });
});
