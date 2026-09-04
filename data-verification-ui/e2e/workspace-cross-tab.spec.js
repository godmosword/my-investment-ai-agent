// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Workspace cross-tab sync (Queue 34 Phase 2)", () => {
  test("layout change in tab A updates Workspace select in tab B", async ({ browser }) => {
    const context = await browser.newContext();
    const pageA = await context.newPage();
    const pageB = await context.newPage();
    try {
      await pageA.goto("/portfolio", { waitUntil: "load" });
      await pageB.goto("/portfolio", { waitUntil: "load" });

      await pageA.getByTestId("global-watchlist-toggle").click();
      await pageB.getByTestId("global-watchlist-toggle").click();
      await expect(pageA.getByTestId("global-watchlist-panel")).toBeVisible({ timeout: 15_000 });
      await expect(pageB.getByTestId("global-watchlist-panel")).toBeVisible({ timeout: 15_000 });

      const selA = pageA.getByTestId("workspace-layout");
      const selB = pageB.getByTestId("workspace-layout");
      await expect(selA).toBeVisible({ timeout: 60_000 });
      await expect(selB).toBeVisible({ timeout: 60_000 });
      await expect(selA.locator('option[value="balanced"]')).toHaveText("均衡");
      await expect(selA.locator('option[value="dense"]')).toHaveText("緊湊");
      await expect(selA.locator('option[value="focus"]')).toHaveText("聚焦");

      await selA.selectOption("focus");
      await expect(selB).toHaveValue("focus", { timeout: 8_000 });
    } finally {
      await context.close();
    }
  });
});
