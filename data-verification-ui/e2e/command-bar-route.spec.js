// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Terminal Command Bar (queue 29)", () => {
  test("AAPL GO sets focus and WATCH persists terminal_sse_watch", async ({ page }) => {
    await page.goto("/briefs", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });

    const loading = page.getByText("載入終端…");
    if ((await loading.count()) > 0) {
      await loading.waitFor({ state: "hidden", timeout: 90_000 }).catch(() => {});
    }

    await page.getByPlaceholder(/AAPL/i).fill("AAPL GO");
    await page.getByRole("button", { name: "GO" }).click();

    // Recent chip renders the symbol as a button; assert the 關注 span instead.
    await expect(bar.locator(".font-mono", { hasText: "AAPL" }).first()).toBeVisible();
    await page.getByRole("button", { name: "WATCH" }).click();

    const watch = await page.evaluate(() =>
      globalThis.localStorage.getItem("terminal_sse_watch"), // TERMINAL_SSE_WATCH_KEY (src/constants/terminalStorage.js)
    );
    expect(watch).toContain("AAPL");
  });

  test("RUN button triggers crew and shows toast", async ({ page }) => {
    await page.goto("/briefs", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });

    const runBtn = page.getByTestId("cmd-bar-run");
    await expect(runBtn).toBeVisible();
    await runBtn.click();

    // Toast appears with job id from mock (e2emock01)
    const toast = page.getByTestId("cmd-bar-run-toast");
    await expect(toast).toBeVisible({ timeout: 5_000 });
    await expect(toast).toContainText("e2emock01");
  });

  test("typing RUN and pressing Enter triggers crew", async ({ page }) => {
    await page.goto("/briefs", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });

    await page.getByPlaceholder(/AAPL/i).fill("RUN");
    await page.getByPlaceholder(/AAPL/i).press("Enter");

    const toast = page.getByTestId("cmd-bar-run-toast");
    await expect(toast).toBeVisible({ timeout: 5_000 });
  });
});
