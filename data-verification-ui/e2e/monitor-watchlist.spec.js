// @ts-check
import { test, expect } from "@playwright/test";

test.describe("FE-3 Portfolio › Monitor tab — watchlist + filter + detail navigation", () => {
  test.beforeEach(async ({ page }) => {
    // Seed the shared watchlist before the app loads.
    await page.addInitScript(() => {
      window.localStorage.setItem("qsi_watchlist", JSON.stringify(["BTC", "SPY", "NVDA"]));
    });
  });

  test("renders rows with live quote and supports search filter", async ({ page }) => {
    await page.goto("/portfolio?tab=monitor", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("watchlist-monitor")).toBeVisible();

    // Three seeded symbols render as rows.
    const rows = page.getByTestId("watchlist-monitor-row");
    await expect(rows).toHaveCount(3);

    // BTC row pulls a price from the mock quote endpoint.
    const btcRow = page.locator('[data-testid="watchlist-monitor-row"][data-symbol="BTC"]');
    await expect(btcRow).toBeVisible();
    await expect(btcRow.locator(".watchlist-monitor__price")).not.toHaveText("—", { timeout: 30_000 });

    // Filter narrows the list client-side without re-fetching.
    await page.getByTestId("watchlist-monitor-filter").fill("BT");
    await expect(rows).toHaveCount(1);
    await expect(page.locator('[data-testid="watchlist-monitor-row"][data-symbol="BTC"]')).toBeVisible();

    // Clearing the filter restores all rows.
    await page.getByTestId("watchlist-monitor-filter").fill("");
    await expect(rows).toHaveCount(3);
  });

  test("clicking a row navigates to /insights?symbol=…", async ({ page }) => {
    await page.goto("/portfolio?tab=monitor", { waitUntil: "load" });
    await expect(page.getByTestId("watchlist-monitor")).toBeVisible({ timeout: 60_000 });

    await page
      .locator('[data-testid="watchlist-monitor-row"][data-symbol="NVDA"] .watchlist-monitor__open')
      .click();

    await expect(page).toHaveURL(/\/insights\?symbol=NVDA/);
  });
});
