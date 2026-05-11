// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Positions route (/positions)", () => {
  test("loads execution intents table from mock API", async ({ page }) => {
    await page.goto("/positions", { waitUntil: "load" });
    await expect(page.getByTestId("positions-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { name: "倉位管理" })).toBeVisible();
    await expect(page.getByTestId("positions-m4-table")).toBeVisible();
    await expect(page.getByTestId("positions-m4-table").getByRole("cell", { name: "NVDA", exact: true })).toBeVisible();
    await expect(page.getByText("e2e-spy-1")).toBeVisible();
    await expect(page.getByRole("cell", { name: "SPY", exact: true })).toBeVisible();
  });
});
