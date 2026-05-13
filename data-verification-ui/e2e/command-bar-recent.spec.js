// @ts-check
import { test, expect } from "@playwright/test";

/**
 * Command Bar — recent symbols history (queue 29 follow-up).
 * After a successful GO, the symbol is pushed onto localStorage
 * (``TERMINAL_RECENT_SYMBOLS_KEY`` in ``src/constants/terminalStorage.js`` — currently ``terminal_recent_symbols``)
 * and rendered as quick-click chips below the bar.
 */
test.describe("Terminal Command Bar — recent symbols", () => {
  test("GO pushes symbol onto recent chips and persists to localStorage", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });

    // Ensure clean slate.
    await page.evaluate(() => globalThis.localStorage.removeItem("terminal_recent_symbols")); // TERMINAL_RECENT_SYMBOLS_KEY

    await page.getByPlaceholder(/AAPL/i).fill("AAPL GO");
    await page.getByRole("button", { name: "GO" }).click();

    const recent = page.getByTestId("terminal-command-recent");
    await expect(recent).toBeVisible();
    await expect(recent.getByRole("button", { name: "AAPL" })).toBeVisible();

    const stored = await page.evaluate(() =>
      globalThis.localStorage.getItem("terminal_recent_symbols"),
    );
    expect(stored).toContain("AAPL");

    // Second symbol — chip ordering newest-first.
    await page.getByPlaceholder(/AAPL/i).fill("NVDA");
    await page.getByRole("button", { name: "GO" }).click();

    const chips = recent.getByRole("button");
    await expect(chips.first()).toHaveText("NVDA");
    await expect(chips.nth(1)).toHaveText("AAPL");

    // Click an existing chip — focus updates, no duplicate added.
    await chips.nth(1).click();
    await expect(bar.locator(".font-mono", { hasText: "AAPL" }).first()).toBeVisible();

    const stored2 = await page.evaluate(() =>
      globalThis.localStorage.getItem("terminal_recent_symbols"),
    );
    // AAPL bumped to front after click, NVDA pushed to position 2; no duplicates.
    expect(stored2).toBe("AAPL,NVDA");
  });
});
