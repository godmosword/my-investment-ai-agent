// @ts-check
import { test, expect } from "@playwright/test";

test.describe("FE-4 Settings hub — gate stats / poll toggle / gate failures", () => {
  test("renders gate stats, poll toggles persist, gate failures list visible", async ({ page }) => {
    await page.goto("/settings", { waitUntil: "load" });

    // Grid wrapper renders.
    await expect(page.getByTestId("settings-grid")).toBeVisible({ timeout: 60_000 });

    // Gate stats card pulls from mocked qsrec-stats (80%).
    await expect(page.getByTestId("settings-pass-rate")).toContainText("80");

    // Polling frequency toggle: select 15s, then verify localStorage + aria-pressed.
    await page.getByTestId("settings-poll-15000").click();
    await expect(page.getByTestId("settings-poll-15000")).toHaveAttribute("aria-pressed", "true");
    const stored = await page.evaluate(() => window.localStorage.getItem("qs_terminal_poll_ms_override"));
    expect(stored).toBe("15000");

    // Clearing restores default.
    await page.getByTestId("settings-poll-clear").click();
    const clearedStored = await page.evaluate(() =>
      window.localStorage.getItem("qs_terminal_poll_ms_override"),
    );
    expect(clearedStored).toBeNull();

    // Gate failures list shows mocked rows.
    await expect(page.getByTestId("settings-gate-failures-list")).toBeVisible();
    const rows = page.getByTestId("settings-gate-failure-row");
    await expect(rows).toHaveCount(2);
    await expect(rows.first()).toContainText("exec_summary 缺 market_regime");
  });

  test("desktop 1280px lays out the grid in 3 columns", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/settings", { waitUntil: "load" });
    await expect(page.getByTestId("settings-grid")).toBeVisible({ timeout: 60_000 });
    const cols = await page.getByTestId("settings-grid").evaluate(
      (el) => getComputedStyle(el).gridTemplateColumns,
    );
    expect(cols.split(" ").length).toBe(3);
  });
});
