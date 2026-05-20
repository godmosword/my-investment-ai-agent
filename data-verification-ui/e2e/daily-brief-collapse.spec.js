// @ts-check
import { test, expect } from "@playwright/test";

test.describe("FE-2 Daily Brief — ticker / gate badge / collapsible cards", () => {
  test("ticker strip renders default symbols", async ({ page }) => {
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });

    const strip = page.getByTestId("ticker-strip");
    await expect(strip).toBeVisible();
    // At least BTC chip is present (mock-api-server serves BTC quote).
    await expect(page.locator('[data-testid="ticker-strip-chip"][data-symbol="BTC"]')).toBeVisible();
  });

  test("section cards collapse and expand via chevron toggle", async ({ page }) => {
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("structured-report-view")).toBeVisible({ timeout: 60_000 });

    const cards = page.getByTestId("brief-section-card");
    await expect(cards.first()).toBeVisible();

    const firstCard = cards.first();
    await expect(firstCard).toHaveAttribute("data-collapsed", "false");

    await firstCard.locator(".brief-section-card__toggle").click();
    await expect(firstCard).toHaveAttribute("data-collapsed", "true");

    // Toggle back to expanded.
    await firstCard.locator(".brief-section-card__toggle").click();
    await expect(firstCard).toHaveAttribute("data-collapsed", "false");
  });

  test("desktop viewport wraps ticker strip", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/report/2026-04-14", { waitUntil: "load" });
    await expect(page.getByTestId("ticker-strip")).toBeVisible({ timeout: 60_000 });

    const flexWrap = await page.getByTestId("ticker-strip").evaluate(
      (el) => getComputedStyle(el).flexWrap,
    );
    expect(flexWrap).toBe("wrap");
  });
});
