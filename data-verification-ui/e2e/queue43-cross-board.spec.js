// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Queue 43 cross-board polish", () => {
  test("command bar jumps boards and symbol lookup deep-links to insights", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });

    await page.getByPlaceholder(/columns/i).fill("columns go");
    await page.getByRole("button", { name: "GO" }).click();
    await expect(page).toHaveURL(/\/columns$/);
    await expect(page.getByTestId("columns-home")).toBeVisible();

    await page.getByPlaceholder(/columns/i).fill("NVDA");
    await page.getByRole("button", { name: "GO" }).click();
    await expect(page).toHaveURL(/\/insights\?symbol=NVDA$/);
    await expect(bar.locator(".font-mono", { hasText: "NVDA" }).first()).toBeVisible();
  });

  test("global watchlist and price alert panel are available outside portfolio", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    await expect(page.getByTestId("global-watchlist-panel")).toBeVisible();
    await page.getByTestId("global-watchlist").getByPlaceholder("新增代號").fill("NVDA");
    await page.getByTestId("global-watchlist").getByRole("button", { name: "Add" }).click();
    await expect(page.getByTestId("global-watchlist")).toContainText("NVDA");

    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible();
    await panel.getByPlaceholder("NVDA").fill("NVDA");
    await panel.getByPlaceholder("900").fill("900");
    await panel.getByRole("button", { name: "Add" }).click();
    await expect(panel).toContainText("NVDA");
  });
});
