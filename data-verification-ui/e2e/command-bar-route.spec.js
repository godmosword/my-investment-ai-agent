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

    const watch = await page.evaluate(() => globalThis.localStorage.getItem("terminal_sse_watch"));
    expect(watch).toContain("AAPL");
  });
});
