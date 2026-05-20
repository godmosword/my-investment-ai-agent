// @ts-check
import { test, expect } from "@playwright/test";

async function expectTargetAtLeast(locator, minPx = 44) {
  await expect(locator).toBeVisible({ timeout: 60_000 });
  const box = await locator.boundingBox();
  expect(box, "interactive element has a bounding box").not.toBeNull();
  expect(box.width, `width for ${await locator.evaluate((el) => el.outerHTML.slice(0, 120))}`).toBeGreaterThanOrEqual(minPx);
  expect(box.height, `height for ${await locator.evaluate((el) => el.outerHTML.slice(0, 120))}`).toBeGreaterThanOrEqual(minPx);
}

test.describe("NEXT-1 touch target smoke", () => {
  test("mobile terminal controls and shared monitor toggle meet 44px minimum", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard", { waitUntil: "load" });

    const bar = page.getByTestId("terminal-command-bar");
    await expectTargetAtLeast(bar.locator("input").first());
    await expectTargetAtLeast(bar.getByRole("button", { name: "GO" }));
    await expectTargetAtLeast(page.getByTestId("cmd-bar-run"));
    await expectTargetAtLeast(bar.getByRole("button", { name: "WATCH" }));
    await expectTargetAtLeast(page.getByTestId("global-watchlist-toggle"));
  });

  test("desktop keeps primary terminal controls at 44px minimum", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/dashboard", { waitUntil: "load" });

    const bar = page.getByTestId("terminal-command-bar");
    await expectTargetAtLeast(bar.locator("input").first());
    await expectTargetAtLeast(bar.getByRole("button", { name: "GO" }));
    await expectTargetAtLeast(page.getByTestId("cmd-bar-run"));
    await expectTargetAtLeast(page.getByTestId("global-watchlist-toggle"));
  });
});
