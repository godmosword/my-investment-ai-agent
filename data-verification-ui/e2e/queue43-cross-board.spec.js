// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Queue 43 cross-board polish", () => {
  test("command bar jumps boards and symbol lookup deep-links to insights", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });
    const commandInput = bar.getByRole("textbox", { name: /terminal command input/i });
    const goButton = bar.getByRole("button", { name: "GO" });

    await commandInput.fill("columns go");
    await goButton.click();
    await expect(page).toHaveURL(/\/columns$/);
    await expect(page.getByTestId("columns-home")).toBeVisible();

    await commandInput.fill("NVDA");
    await goButton.click();
    await expect(page).toHaveURL(/\/insights\?symbol=NVDA$/);
    await expect(bar.locator(".font-mono", { hasText: "NVDA" }).first()).toBeVisible();
  });

  test("global watchlist and price alert panel are available outside portfolio", async ({ page }) => {
    await page.goto("/news", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    await expect(page.getByTestId("global-watchlist-panel")).toBeVisible();
    await page.getByTestId("global-watchlist").getByPlaceholder("新增代號").fill("NVDA");
    await page.getByTestId("global-watchlist").getByTestId("watchlist-add").click();
    await expect(page.getByTestId("global-watchlist")).toContainText("NVDA");

    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible();
    await panel.getByPlaceholder("NVDA").fill("NVDA");
    await panel.getByPlaceholder("900").fill("900");
    await panel.getByTestId("price-alerts-add").click();
    await expect(panel).toContainText("NVDA");

    const workspace = page.getByTestId("workspace-panel");
    await expect(workspace).toBeVisible();
    await expect(workspace.getByTestId("workspace-digest")).toContainText("$8,000");
    await expect(workspace.getByTestId("workspace-window-grid")).toContainText("Portfolio");
    await workspace.getByTestId("workspace-layout").selectOption("dense");
    await expect(workspace).toContainText("Workspace layout saved");
    await workspace.getByRole("button", { name: "Up" }).last().click();
    await expect(workspace).toContainText("Workspace panels saved");
    await workspace
      .getByTestId("workspace-import-text")
      .fill('{"version":1,"keys":{"qsi_watchlist":"[\\"MSFT\\"]","terminal_recent_symbols":"MSFT","qs_workspace_layout":"focus","qs_workspace_panels":"[\\"portfolio\\",\\"alerts\\"]"}}');
    await workspace.getByTestId("workspace-import").click();
    await expect(workspace).toContainText("工作區已匯入");
    await expect(page.getByTestId("global-watchlist")).toContainText("MSFT");
  });
});
