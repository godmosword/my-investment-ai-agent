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

  test("price alerts row delete is 移除, ≥44px, and still deletes", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await panel.getByPlaceholder("NVDA").fill("AAPL");
    await panel.getByPlaceholder("900").fill("180");
    await panel.getByTestId("price-alerts-add").click();

    const row = panel.getByTestId("price-alerts-row");
    await expect(row).toBeVisible();
    await expect(row).toContainText("AAPL");

    const remove = row.getByTestId("price-alerts-remove");
    await expect(remove).toHaveText("移除");
    const box = await remove.boundingBox();
    expect(box, "Remove button has a bounding box").not.toBeNull();
    expect(box.height).toBeGreaterThanOrEqual(44);

    await remove.click();
    await expect(panel.getByTestId("price-alerts-row")).toHaveCount(0);
    await expect(panel).not.toContainText("AAPL");
  });

  test("price alerts loading and empty states are Traditional Chinese", async ({ page }) => {
    /** @type {(() => void) | undefined} */
    let releaseGet;
    const holdGet = new Promise((resolve) => {
      releaseGet = resolve;
    });
    await page.route("**/api/push/price-alerts", async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      await holdGet;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ alerts: [] }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const loadingPanel = page.getByTestId("price-alerts-panel");
    await expect(loadingPanel).toBeVisible({ timeout: 60_000 });
    const loading = loadingPanel.getByTestId("price-alerts-loading");
    await expect(loading).toBeVisible();
    await expect(loading).toHaveText("載入警示…");
    await expect(loadingPanel.getByTestId("price-alerts-empty")).toHaveCount(0);
    await expect(loadingPanel.getByTestId("price-alerts-row")).toHaveCount(0);
    await expect(loadingPanel).not.toContainText("alerts");
    releaseGet?.();
  });

  test("price alerts empty, triggered, and row direction are Traditional Chinese", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel.getByTestId("price-alerts-empty")).toHaveText("尚無價格警示。");
    await expect(panel).not.toContainText("price alert");
    await expect(panel.getByTestId("price-alerts-loading")).toHaveCount(0);

    await panel.getByPlaceholder("NVDA").fill("NVDA");
    await panel.getByPlaceholder("900").fill("900");
    await panel.getByTestId("price-alerts-add").click();
    const aboveRow = panel.getByTestId("price-alerts-row").filter({ hasText: "NVDA" });
    await expect(aboveRow.getByTestId("price-alerts-row-direction")).toContainText("高於");
    await expect(aboveRow.getByTestId("price-alerts-row-direction")).not.toContainText("above");

    await panel.getByTestId("price-alerts-direction").selectOption("below");
    await panel.getByPlaceholder("NVDA").fill("MSFT");
    await panel.getByPlaceholder("900").fill("100");
    await panel.getByTestId("price-alerts-add").click();
    const belowRow = panel.getByTestId("price-alerts-row").filter({ hasText: "MSFT" });
    await expect(belowRow.getByTestId("price-alerts-row-direction")).toContainText("低於");
    await expect(belowRow.getByTestId("price-alerts-row-direction")).not.toContainText("below");

    await panel.getByTestId("price-alerts-check").click();
    await expect(aboveRow.getByTestId("price-alerts-triggered")).toHaveText("已觸發");
    await expect(belowRow.getByTestId("price-alerts-triggered")).toHaveCount(0);
    await expect(panel).not.toContainText("triggered");
    await expect(aboveRow).not.toContainText("above");
    await expect(belowRow).not.toContainText("below");
  });
});
