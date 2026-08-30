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

  test("missing regime_score shows UNKNOWN, not invented 0", async ({ page }) => {
    await page.route(
      (url) => url.pathname === "/api/industries/themes" || url.pathname.startsWith("/api/industries/themes"),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            themes: [],
            rotation: [{ id: "missing-score", label: "缺分數板塊", symbols: ["TEST"] }],
            source: "e2e",
          }),
        });
      },
    );

    await page.goto("/columns", { waitUntil: "load" });
    await expect(page.getByTestId("columns-home")).toBeVisible({ timeout: 60_000 });
    await page.locator("summary").filter({ hasText: "板塊輪動與相關主題" }).click();
    const row = page.getByTestId("columns-rotation-row").first();
    await expect(row).toBeVisible();
    await expect(row).toContainText("缺分數板塊");
    await expect(row).toContainText("UNKNOWN");
    await expect(row).not.toContainText("+0");
  });

  test("switches to crypto pillar", async ({ page }) => {
    await page.goto("/columns", { waitUntil: "load" });
    await page.getByTestId("columns-pillar-crypto").click();

    await expect(page.getByTestId("columns-deep-card").first()).toContainText("Bitcoin ETF 資金流回溫");
    await expect(page.getByText("cointelegraph.com")).toBeVisible();
  });
});
