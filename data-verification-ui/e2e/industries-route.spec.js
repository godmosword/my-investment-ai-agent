// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Columns route /columns", () => {
  test("loads pillar deep briefs, related themes, and side panel", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("columns-pillar-semiconductor").click();
    await expect(page.getByTestId("columns-deep-card").first()).toContainText("AI 半導體供應鏈拉高資本支出");
    await expect(page.getByText("semianalysis.com")).toBeVisible();
    await expect(page.getByText("4 min read")).toBeVisible();
    await page.locator("summary").filter({ hasText: "板塊輪動與相關主題" }).click();
    await expect(page.getByTestId("columns-sector-rotation")).toBeVisible();
    await expect(page.getByTestId("columns-rotation-row").first()).toContainText("AI 半導體");
    await expect(page.getByTestId("columns-theme-card").first()).toBeVisible();

    await page.getByTestId("columns-deep-card").first().click();
    await expect(page.getByTestId("columns-deep-panel")).toBeVisible();
    await expect(page.getByText("HBM 需求偏強")).toBeVisible();
    await expect(page.getByTestId("columns-ticker-chip").filter({ hasText: "NVDA" })).toHaveAttribute(
      "href",
      "/insights?symbol=NVDA",
    );
  });

  test("switches to crypto pillar", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await page.getByTestId("columns-pillar-crypto").click();

    await expect(page.getByTestId("columns-deep-card").first()).toContainText("Bitcoin ETF 資金流回溫");
    await expect(page.getByText("cointelegraph.com")).toBeVisible();
  });
});
