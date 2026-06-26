// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Portfolio route (/portfolio)", () => {
  test("loads holdings, KPIs, and tracker actions", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });

    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("portfolio-source-badge")).toContainText("jsonl");
    await expect(page.getByTestId("portfolio-total-value")).toContainText("$8,000");
    await expect(page.getByTestId("portfolio-holdings-table").getByRole("cell", { name: "NVDA", exact: true })).toBeVisible();
    await expect(page.getByTestId("portfolio-add-button")).toBeVisible();
    await expect(page.getByTestId("portfolio-import-button")).toBeVisible();
  });

  test("allocation donut renders slices from holdings (VU2)", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const donut = page.getByTestId("allocation-donut");
    await expect(donut).toBeVisible();
    await expect(donut.locator('[data-symbol="NVDA"]')).toBeVisible();
    await expect(page.getByTestId("allocation-slice").first()).toBeVisible();
  });
});
