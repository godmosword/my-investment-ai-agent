// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Columns — bilingual commentary (queue 45 · P4)", () => {
  test("shows zh/en toggle when both commentary fields exist", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });

    // Pillar "semiconductor" includes the e2e-ai-chip mock item which has both
    // commentary_zh and commentary_en.
    await page.getByTestId("columns-pillar-semiconductor").click();
    const card = page.getByTestId("columns-deep-card").first();
    await expect(card).toBeVisible({ timeout: 15_000 });
    await card.click();

    const panel = page.getByTestId("columns-deep-panel");
    await expect(panel).toBeVisible();

    const toggle = page.getByTestId("columns-commentary-toggle");
    await expect(toggle).toBeVisible();
    const commentary = page.getByTestId("columns-commentary-text");
    await expect(commentary).toContainText("HBM");

    await page.getByTestId("columns-commentary-en").click();
    await expect(commentary).toContainText(/Supply chain/i);
    await page.getByTestId("columns-commentary-zh").click();
    await expect(commentary).toContainText("供應鏈");
  });
});
