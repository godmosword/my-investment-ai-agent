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

  test("edit button opens IntentUpdateModal (Q30)", async ({ page }) => {
    await page.goto("/positions", { waitUntil: "load" });
    await expect(page.getByTestId("positions-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("e2e-spy-1")).toBeVisible();

    // Click the edit button for the first intent row
    await page.getByTestId("intent-edit-e2e-spy-1").click();

    const modal = page.getByTestId("intent-update-modal");
    await expect(modal).toBeVisible({ timeout: 5_000 });
    await expect(modal.getByTestId("intent-status-select")).toBeVisible();
    await expect(modal.getByTestId("intent-update-submit")).toBeVisible();
  });

  test("IntentUpdateModal PATCH submits and closes (Q30)", async ({ page }) => {
    await page.goto("/positions", { waitUntil: "load" });
    await expect(page.getByText("e2e-spy-1")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("intent-edit-e2e-spy-1").click();
    const modal = page.getByTestId("intent-update-modal");
    await expect(modal).toBeVisible({ timeout: 5_000 });

    // Change status and submit
    await modal.getByTestId("intent-status-select").selectOption("APPROVED_FOR_PAPER");
    await modal.getByTestId("intent-update-submit").click();

    // Modal should close after successful PATCH
    await expect(modal).not.toBeVisible({ timeout: 5_000 });
  });
});
