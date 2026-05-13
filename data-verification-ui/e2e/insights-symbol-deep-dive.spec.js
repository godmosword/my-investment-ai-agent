import { expect, test } from "@playwright/test";

test.describe("Insights symbol deep dive", () => {
  test("renders analysis bundle when symbol query param is present", async ({ page }) => {
    await page.goto("/insights?symbol=NVDA", { waitUntil: "load" });
    await expect(page.getByTestId("symbol-deep-dive")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("NVDA");
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("$100.50");
    await expect(page.getByTestId("symbol-deep-dive")).toContainText("e2e_mock");
  });
});
