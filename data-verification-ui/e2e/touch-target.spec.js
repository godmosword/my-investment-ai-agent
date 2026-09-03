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

  test("watchlist remove control meets 44px minimum and still removes a symbol", async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("qsi_watchlist", JSON.stringify(["NVDA"]));
    });
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const watchlist = page.getByTestId("global-watchlist");
    await expect(watchlist).toBeVisible({ timeout: 60_000 });
    await expect(watchlist.getByTestId("watchlist-add")).toHaveText("新增");
    await expect(watchlist).toContainText("NVDA");

    const remove = watchlist.getByTestId("watchlist-remove");
    await expectTargetAtLeast(remove);
    await remove.click();
    await expect(watchlist.getByTestId("watchlist-remove")).toHaveCount(0);
    await expect(watchlist).not.toContainText("NVDA");
  });

  test("price alerts Check control meets 44px minimum height", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const check = page.getByTestId("price-alerts-check");
    await expectTargetAtLeast(check);
    await expect(check).toHaveText("檢查");
  });
});
