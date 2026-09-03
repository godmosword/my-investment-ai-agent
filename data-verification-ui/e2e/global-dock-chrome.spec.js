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
});
