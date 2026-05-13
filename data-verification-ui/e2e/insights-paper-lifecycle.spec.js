import { expect, test } from "@playwright/test";

test.describe("Insights paper lifecycle", () => {
  test("renders paper lifecycle summary, table, create form, and blotter", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await page.getByTestId("insights-tab-paper").click();

    await expect(page.getByTestId("paper-lifecycle-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("paper-kpi-active")).toContainText("1");
    await expect(page.getByTestId("paper-kpi-realized")).toContainText("+10.0%");
    await expect(page.getByTestId("paper-lifecycle-table").getByText("NVDA", { exact: true })).toBeVisible();
    await expect(page.getByTestId("paper-intent-create-toggle")).toBeVisible();
    await expect(page.getByText("執行意圖（紙上前置）")).toBeVisible();

    await page.getByTestId("paper-intent-create-toggle").click();
    await page.getByTestId("paper-intent-asset").fill("msft");
    await page.getByTestId("paper-intent-create-submit").click();
    await expect(page.getByTestId("paper-intent-create-toggle")).toContainText("+ 新增意圖");
  });
});
