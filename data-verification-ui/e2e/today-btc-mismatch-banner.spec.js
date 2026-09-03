// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Bloomberg §6 — Dashboard BTC price_alignment banner", () => {
  test("shows non-silent banner when mock returns aligned=false (e2e_btc_misaligned)", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("e2e_btc_misaligned", "1");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("today-btc-price-mismatch-banner")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("today-btc-price-aligned")).toContainText(/對齊警告/);
    await expect(page.getByTestId("today-btc-quote-last")).toBeVisible();
    const quoteText = await page.getByTestId("today-btc-quote-last").innerText();
    expect(quoteText.replace(/\s/g, "")).toMatch(/50,150\.25/);
  });

  test("depth tab still shows mismatch banner (not overview-only)", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("e2e_btc_misaligned", "1");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-tab-depth")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByTestId("today-btc-snapshot-strip")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("today-btc-price-mismatch-banner")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("today-btc-price-aligned")).toContainText(/對齊警告/);
  });

  test("shows N/A state when backend cannot confirm price_alignment", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem("e2e_btc_alignment_na", "1");
      } catch {
        /* ignore */
      }
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("today-btc-price-aligned")).toContainText(/對齊狀態：N\/A/);
    await expect(page.getByTestId("today-btc-price-alignment-na-banner")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("today-btc-quote-last")).toContainText(/50,000\.125/);
  });
});
