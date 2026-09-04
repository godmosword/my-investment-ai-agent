// @ts-check
import { test, expect } from "@playwright/test";

test.describe("ITER-P4-44F global dock chrome", () => {
  test("primary dock copy is Traditional Chinese", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    const toggle = page.getByTestId("global-watchlist-toggle");
    await expect(toggle).toBeVisible({ timeout: 60_000 });
    await expect(toggle).toHaveText("監控清單");
    await expect(toggle).toHaveAttribute("aria-label", "開啟共享監控");

    await toggle.click();
    const panel = page.getByTestId("global-watchlist-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("global-watchlist-title")).toHaveText("共享監控");
    await expect(page.getByTestId("global-watchlist-close")).toHaveText("關閉");
    await expect(toggle).toHaveAttribute("aria-label", "關閉共享監控");
    await expect(panel).not.toContainText("Shared Monitor");
    await expect(page.getByTestId("global-watchlist-close")).not.toHaveText("Close");

    await page.getByTestId("global-watchlist-close").click();
    await expect(panel).toHaveCount(0);
    await expect(toggle).toHaveAttribute("aria-label", "開啟共享監控");
  });

  test("price alerts Check is ≥44px with zh title, 新增, and 高於／低於", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel.locator(".card-title")).toHaveText("價格警示");
    await expect(panel).toContainText("Web Push 觸發佇列 · 僅模擬");

    const check = panel.getByTestId("price-alerts-check");
    await expect(check).toHaveText("檢查");
    const box = await check.boundingBox();
    expect(box, "Check button has a bounding box").not.toBeNull();
    expect(box.height).toBeGreaterThanOrEqual(44);

    await expect(panel.getByTestId("price-alerts-add")).toHaveText("新增");
    const direction = panel.getByTestId("price-alerts-direction");
    await expect(direction.locator('option[value="above"]')).toHaveText("高於");
    await expect(direction.locator('option[value="below"]')).toHaveText("低於");
    await expect(direction).toHaveValue("above");
  });

  test("price alerts row delete is 移除, ≥44px, and still deletes", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await panel.getByPlaceholder("NVDA").fill("AAPL");
    await panel.getByPlaceholder("900").fill("180");
    await panel.getByTestId("price-alerts-add").click();

    const row = panel.getByTestId("price-alerts-row");
    await expect(row).toBeVisible();
    await expect(row).toContainText("AAPL");

    const remove = row.getByTestId("price-alerts-remove");
    await expect(remove).toHaveText("移除");
    const box = await remove.boundingBox();
    expect(box, "Remove button has a bounding box").not.toBeNull();
    expect(box.height).toBeGreaterThanOrEqual(44);

    await remove.click();
    await expect(panel.getByTestId("price-alerts-row")).toHaveCount(0);
    await expect(panel).not.toContainText("AAPL");
  });

  test("price alerts loading and empty states are Traditional Chinese", async ({ page }) => {
    /** @type {(() => void) | undefined} */
    let releaseGet;
    const holdGet = new Promise((resolve) => {
      releaseGet = resolve;
    });
    await page.route("**/api/push/price-alerts", async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }
      await holdGet;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ alerts: [] }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const loadingPanel = page.getByTestId("price-alerts-panel");
    await expect(loadingPanel).toBeVisible({ timeout: 60_000 });
    const loading = loadingPanel.getByTestId("price-alerts-loading");
    await expect(loading).toBeVisible();
    await expect(loading).toHaveText("載入警示…");
    await expect(loadingPanel.getByTestId("price-alerts-empty")).toHaveCount(0);
    await expect(loadingPanel.getByTestId("price-alerts-row")).toHaveCount(0);
    await expect(loadingPanel).not.toContainText("alerts");
    releaseGet?.();
  });

  test("price alerts empty, triggered, and row direction are Traditional Chinese", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel.getByTestId("price-alerts-empty")).toHaveText("尚無價格警示。");
    await expect(panel).not.toContainText("price alert");
    await expect(panel.getByTestId("price-alerts-loading")).toHaveCount(0);

    await panel.getByPlaceholder("NVDA").fill("NVDA");
    await panel.getByPlaceholder("900").fill("900");
    await panel.getByTestId("price-alerts-add").click();
    const aboveRow = panel.getByTestId("price-alerts-row").filter({ hasText: "NVDA" });
    await expect(aboveRow.getByTestId("price-alerts-row-direction")).toContainText("高於");
    await expect(aboveRow.getByTestId("price-alerts-row-direction")).not.toContainText("above");

    await panel.getByTestId("price-alerts-direction").selectOption("below");
    await panel.getByPlaceholder("NVDA").fill("MSFT");
    await panel.getByPlaceholder("900").fill("100");
    await panel.getByTestId("price-alerts-add").click();
    const belowRow = panel.getByTestId("price-alerts-row").filter({ hasText: "MSFT" });
    await expect(belowRow.getByTestId("price-alerts-row-direction")).toContainText("低於");
    await expect(belowRow.getByTestId("price-alerts-row-direction")).not.toContainText("below");

    await panel.getByTestId("price-alerts-check").click();
    await expect(aboveRow.getByTestId("price-alerts-triggered")).toHaveText("已觸發");
    await expect(belowRow.getByTestId("price-alerts-triggered")).toHaveCount(0);
    await expect(panel).not.toContainText("triggered");
    await expect(aboveRow).not.toContainText("above");
    await expect(belowRow).not.toContainText("below");
  });
});

test.describe("ITER-P4-44I workspace dock zh + touch", () => {
  test("workspace export/import are 匯出／匯入, ≥44px, and still export/import", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const workspace = page.getByTestId("workspace-panel");
    await expect(workspace).toBeVisible({ timeout: 60_000 });

    const exp = workspace.getByTestId("workspace-export");
    await expect(exp).toHaveText("匯出");
    const expBox = await exp.boundingBox();
    expect(expBox, "Export button has a bounding box").not.toBeNull();
    expect(expBox.height).toBeGreaterThanOrEqual(44);

    const imp = workspace.getByTestId("workspace-import");
    await expect(imp).toHaveText("匯入");
    const impBox = await imp.boundingBox();
    expect(impBox, "Import button has a bounding box").not.toBeNull();
    expect(impBox.height).toBeGreaterThanOrEqual(44);

    await expect(workspace).not.toContainText("Export");
    await expect(imp).not.toHaveText("Import");

    const downloadPromise = page.waitForEvent("download");
    await exp.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("qsi-workspace.json");
    await expect(workspace.getByRole("status")).toHaveText("工作區已匯出");

    await workspace
      .getByTestId("workspace-import-text")
      .fill('{"version":1,"keys":{"qs_workspace_layout":"focus"}}');
    await imp.click();
    await expect(workspace.getByRole("status")).toHaveText("工作區已匯入");
    await expect(workspace.getByTestId("workspace-layout")).toHaveValue("focus");
  });

  test("workspace panel 上移／下移 are ≥44px and still reorder", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const workspace = page.getByTestId("workspace-panel");
    await expect(workspace).toBeVisible({ timeout: 60_000 });

    const up = workspace.getByTestId("workspace-panel-up-portfolio");
    const down = workspace.getByTestId("workspace-panel-down-portfolio");
    await expect(up).toHaveText("上移");
    await expect(down).toHaveText("下移");
    const upBox = await up.boundingBox();
    const downBox = await down.boundingBox();
    expect(upBox, "上移 has a bounding box").not.toBeNull();
    expect(downBox, "下移 has a bounding box").not.toBeNull();
    expect(upBox.height).toBeGreaterThanOrEqual(44);
    expect(downBox.height).toBeGreaterThanOrEqual(44);

    await expect(workspace.getByTestId("workspace-panel-up-paper")).toBeDisabled();
    await expect(workspace.getByTestId("workspace-panel-down-alerts")).toBeDisabled();
    await expect(up).not.toHaveText("Up");
    await expect(down).not.toHaveText("Down");

    await up.click();
    const tiles = workspace.locator('[data-testid^="workspace-panel-tile-"]');
    await expect(tiles.nth(0)).toHaveAttribute("data-testid", "workspace-panel-tile-portfolio");
    await expect(tiles.nth(1)).toHaveAttribute("data-testid", "workspace-panel-tile-paper");

    await workspace.getByTestId("workspace-panel-down-portfolio").click();
    await expect(tiles.nth(0)).toHaveAttribute("data-testid", "workspace-panel-tile-paper");
    await expect(tiles.nth(1)).toHaveAttribute("data-testid", "workspace-panel-tile-portfolio");
  });

  test("workspace title, subtitle, layout, and panel labels are Traditional Chinese", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const workspace = page.getByTestId("workspace-panel");
    await expect(workspace).toBeVisible({ timeout: 60_000 });
    await expect(workspace.getByTestId("workspace-title")).toHaveText("工作區");
    await expect(workspace.getByTestId("workspace-subtitle")).toHaveText("本機版面 · 面板順序 · 跨板塊摘要");
    await expect(workspace.getByTestId("workspace-layout-label")).toContainText("版面");

    const layout = workspace.getByTestId("workspace-layout");
    await expect(layout.locator('option[value="balanced"]')).toHaveText("均衡");
    await expect(layout.locator('option[value="dense"]')).toHaveText("緊湊");
    await expect(layout.locator('option[value="focus"]')).toHaveText("聚焦");
    await expect(layout).toHaveValue("balanced");

    const windows = workspace.getByTestId("workspace-window-grid");
    await expect(windows).toContainText("模擬單");
    await expect(windows).toContainText("持倉");
    await expect(windows).toContainText("專欄");
    await expect(windows).toContainText("警示");
    await expect(workspace.getByTestId("workspace-digest")).toContainText("持倉");
    await expect(workspace.getByTestId("workspace-title")).not.toHaveText("Workspace");
    await expect(windows).not.toContainText("Portfolio");
    await expect(windows).not.toContainText("Columns");
    await expect(layout.locator('option[value="balanced"]')).not.toHaveText("balanced");
  });

  test("workspace digest and windows status copy is Traditional Chinese", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const workspace = page.getByTestId("workspace-panel");
    await expect(workspace).toBeVisible({ timeout: 60_000 });

    const digest = workspace.getByTestId("workspace-digest");
    await expect(workspace.getByTestId("workspace-digest-heading")).toHaveText("摘要");
    await expect(workspace.getByTestId("workspace-windows-heading")).toHaveText("視窗");
    await expect(workspace.getByTestId("workspace-digest-paper-active")).toHaveText(/^\d+ 進行中$/);
    await expect(workspace.getByTestId("workspace-digest-paper-closed")).toHaveText(/^\d+ 已結$/);
    await expect(workspace.getByTestId("workspace-digest-alerts-total")).toHaveText(/^\d+ 合計$/);
    await expect(workspace.getByTestId("workspace-digest-alerts-triggered")).toHaveText(/^\d+ 已觸發$/);
    await expect(workspace.getByTestId("workspace-digest-alerts-pending")).toHaveText(/^\d+ 待觸發$/);
    await expect(workspace.getByTestId("workspace-windows-active")).toHaveText(/^\d+ 進行中$/);
    await expect(digest.getByTestId("workspace-alert-digest-asof")).toContainText("摘要時間");

    await expect(digest).not.toContainText("Digest");
    await expect(digest).not.toContainText("active");
    await expect(digest).not.toContainText("closed");
    await expect(digest).not.toContainText("triggered");
    await expect(digest).not.toContainText("pending");
    await expect(digest).not.toContainText("total");
    await expect(workspace.getByTestId("workspace-window-grid")).not.toContainText("Windows");
    await expect(digest).not.toContainText("as_of");
  });

  test("watchlist title is 觀察清單 and alert success is 警示已建立", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();

    const watchlist = page.getByTestId("global-watchlist");
    await expect(watchlist).toBeVisible({ timeout: 60_000 });
    await expect(watchlist.getByTestId("watchlist-title")).toHaveText("觀察清單");
    await expect(watchlist.getByTestId("watchlist-title")).not.toHaveText("Watchlist");

    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible();
    await panel.getByPlaceholder("NVDA").fill("TSLA");
    await panel.getByPlaceholder("900").fill("200");
    await panel.getByTestId("price-alerts-add").click();
    await expect(panel.getByTestId("price-alerts-status")).toHaveText("警示已建立");
    await expect(panel).not.toContainText("Alert 已建立");
    await expect(panel.getByTestId("price-alerts-row").filter({ hasText: "TSLA" })).toBeVisible();
  });
});

function isPriceAlertsCheckPath(pathname) {
  return pathname === "/api/push/price-alerts/check" || pathname === "/api/push/price-alerts/check/";
}

test.describe("ITER-P4-44J price alerts honesty", () => {
  test("check success with null/omitted checked and triggered shows UNKNOWN, not 0", async ({ page }) => {
    await page.route(
      (url) => isPriceAlertsCheckPath(url.pathname),
      async (route) => {
        if (route.request().method() !== "POST") {
          await route.fallback();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ checked: null, alerts: [], push_results: [] }),
        });
      },
    );

    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await panel.getByTestId("price-alerts-check").click();

    const status = panel.getByTestId("price-alerts-status");
    await expect(status).toHaveText("已檢查 UNKNOWN 筆，觸發 UNKNOWN 筆");
    await expect(status).not.toHaveText(/已檢查 0 筆/);
    await expect(status).not.toHaveText(/觸發 0 筆/);
  });

  test("check success with real 0 stays 0", async ({ page }) => {
    await page.route(
      (url) => isPriceAlertsCheckPath(url.pathname),
      async (route) => {
        if (route.request().method() !== "POST") {
          await route.fallback();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ checked: 0, triggered: 0, alerts: [], push_results: [] }),
        });
      },
    );

    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await panel.getByTestId("price-alerts-check").click();

    const status = panel.getByTestId("price-alerts-status");
    await expect(status).toHaveText("已檢查 0 筆，觸發 0 筆");
    await expect(status).not.toContainText("UNKNOWN");
  });

  test("missing/non-finite target price is UNKNOWN not em dash; real 0 stays $0.00", async ({ page }) => {
    await page.route(
      (url) => url.pathname === "/api/push/price-alerts" || url.pathname === "/api/push/price-alerts/",
      async (route) => {
        if (route.request().method() !== "GET") {
          await route.fallback();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            alerts: [
              {
                id: "alert-null-price",
                symbol: "NULLP",
                direction: "above",
                target_price: null,
                created_at: "2026-05-13T00:00:00Z",
                triggered_at: "",
              },
              {
                id: "alert-omit-price",
                symbol: "OMITP",
                direction: "below",
                created_at: "2026-05-13T00:00:00Z",
                triggered_at: "",
              },
              {
                id: "alert-nan-price",
                symbol: "NANP",
                direction: "above",
                target_price: "n/a",
                created_at: "2026-05-13T00:00:00Z",
                triggered_at: "",
              },
              {
                id: "alert-zero-price",
                symbol: "ZEROP",
                direction: "above",
                target_price: 0,
                created_at: "2026-05-13T00:00:00Z",
                triggered_at: "",
              },
            ],
          }),
        });
      },
    );

    await page.goto("/dashboard", { waitUntil: "load" });
    await page.getByTestId("global-watchlist-toggle").click();
    const panel = page.getByTestId("price-alerts-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });

    const row = (sym) => panel.getByTestId("price-alerts-row").filter({ hasText: sym });
    await expect(row("NULLP").getByTestId("price-alerts-row-price")).toHaveText("UNKNOWN");
    await expect(row("OMITP").getByTestId("price-alerts-row-price")).toHaveText("UNKNOWN");
    await expect(row("NANP").getByTestId("price-alerts-row-price")).toHaveText("UNKNOWN");
    await expect(row("ZEROP").getByTestId("price-alerts-row-price")).toHaveText("$0.00");
    await expect(row("ZEROP").getByTestId("price-alerts-row-price")).not.toHaveText("UNKNOWN");
    await expect(panel).not.toContainText("—");
  });
});
