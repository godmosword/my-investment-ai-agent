// @ts-check
import { test, expect } from "@playwright/test";

test.describe("ITER-P4-44F global dock chrome", () => {
  test("primary dock copy is Traditional Chinese", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    const toggle = page.getByTestId("global-watchlist-toggle");
    await expect(toggle).toBeVisible({ timeout: 60_000 });
    await expect(toggle).toHaveText("監控清單");
    await expect(toggle).toHaveAttribute("aria-label", "開啟共享監控");

    await toggle.click();
    const panel = page.getByTestId("global-watchlist-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("global-watchlist-title")).toHaveText("共享監控");
    await expect(page.getByTestId("global-watchlist-close")).toHaveText("關閉");
    await expect(toggle).toHaveAttribute("aria-label", "關閉共享監控");
    await expect(panel).not.toContainText("Shared Monitor");
    await expect(page.getByTestId("global-watchlist-close")).not.toHaveText("Close");

    await page.getByTestId("global-watchlist-close").click();
    await expect(panel).toHaveCount(0);
    await expect(toggle).toHaveAttribute("aria-label", "開啟共享監控");
  });

  test("price alerts Check is ≥44px with zh title, 新增, and 高於／低於", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel.locator(".card-title")).toHaveText("價格警示");
    await expect(panel).toContainText("Web Push 觸發佇列 · 僅模擬");

    const check = panel.getByTestId("price-alerts-check");
    await expect(check).toHaveText("檢查");
    const box = await check.boundingBox();
    expect(box, "Check button has a bounding box").not.toBeNull();
    expect(box.height).toBeGreaterThanOrEqual(44);

    await expect(panel.getByTestId("price-alerts-add")).toHaveText("新增");
    const direction = panel.getByTestId("price-alerts-direction");
    await expect(direction.locator('option[value="above"]')).toHaveText("高於");
    await expect(direction.locator('option[value="below"]')).toHaveText("低於");
    await expect(direction).toHaveValue("above");
  });
});
