// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Skip link (Portal Phase 4 P2)", () => {
  test("skip link focuses main content landmark", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    const skip = page.locator("a.skip-to-main");
    await expect(skip).toHaveAttribute("href", "#main-content");
    await skip.focus();
    await expect(skip).toBeFocused();
    await skip.click();
    const main = page.locator("#main-content");
    await expect(main).toBeVisible();
    await expect(main).toBeFocused();
  });
});
