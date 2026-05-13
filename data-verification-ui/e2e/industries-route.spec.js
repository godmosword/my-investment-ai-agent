// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Columns route /columns (Q31)", () => {
  test("loads industry themes and sector rotation panel", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });

    // M5 API card
    await expect(page.getByTestId("industries-m5-api")).toBeVisible({ timeout: 60_000 });

    // Sector Rotation panel renders theme chips from mock
    await expect(page.getByTestId("sector-rotation-panel")).toBeVisible();
    await expect(page.getByTestId("sector-rotation-panel")).toContainText("AI 半導體（e2e）");
    await expect(page.getByTestId("sector-rotation-panel")).toContainText("清潔能源（e2e）");
    await expect(page.getByTestId("sector-rotation-panel")).toContainText("金融（e2e）");
  });

  test("sector rotation chips have regime labels", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    const panel = page.getByTestId("sector-rotation-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });

    // AI semis has regime_score=4 → 多 label
    await expect(panel.locator("div", { hasText: "AI 半導體（e2e）" }).first()).toContainText("多");
    // Financials has regime_score=-1 → 空 label
    await expect(panel.locator("div", { hasText: "金融（e2e）" }).first()).toContainText("空");
  });
});
