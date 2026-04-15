// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Bloomberg §6 — Today BTC price_alignment banner", () => {
  test("shows non-silent banner when mock returns aligned=false (e2e_btc_misaligned)", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("e2e_btc_misaligned", "1");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/", { waitUntil: "load" });
    await expect(page.getByTestId("today-btc-price-mismatch-banner")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("today-btc-price-aligned")).toContainText(/對齊警告/);
    await expect(page.getByTestId("today-btc-quote-last")).toBeVisible();
    const quoteText = await page.getByTestId("today-btc-quote-last").innerText();
    expect(quoteText.replace(/\s/g, "")).toMatch(/50,150\.25/);
  });
});
