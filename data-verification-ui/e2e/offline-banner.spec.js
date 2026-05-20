// @ts-check
import { test, expect } from "@playwright/test";

test.describe("FE-6 offline banner — Daily Brief + Watchlist Monitor", () => {
  test("mobile 375px shows today-offline-banner on the report viewer", async ({ page, context }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });

    // Online → banner hidden.
    await expect(page.getByTestId("today-offline-banner")).toHaveCount(0);

    // Flip to offline → banner renders.
    await context.setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    await expect(page.getByTestId("today-offline-banner")).toBeVisible();

    // Restore online → banner hides again.
    await context.setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await expect(page.getByTestId("today-offline-banner")).toHaveCount(0);
  });

  test("watchlist monitor shows its offline banner when offline", async ({ page, context }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem("qsi_watchlist", JSON.stringify(["BTC"]));
    });
    await page.goto("/portfolio?tab=monitor", { waitUntil: "load" });
    await expect(page.getByTestId("watchlist-monitor")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("watchlist-monitor-offline-banner")).toHaveCount(0);

    await context.setOffline(true);
    await page.evaluate(() => window.dispatchEvent(new Event("offline")));
    await expect(page.getByTestId("watchlist-monitor-offline-banner")).toBeVisible();

    await context.setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
  });
});
