// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Bloomberg §6 — BTC price across Dashboard vs Insights", () => {
  test("Dashboard snapshot strip matches Insights quote last (mock API)", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("today-btc-quote-last")).toBeVisible({ timeout: 60_000 });
    const todayText = await page.getByTestId("today-btc-quote-last").innerText();
    expect(todayText.replace(/\s/g, "")).toMatch(/50,000\.125/);

    await page.goto("/insights?e2e_btc=1", { waitUntil: "load" });
    const loading = page.getByText("載入終端…");
    if ((await loading.count()) > 0) {
      await loading.waitFor({ state: "hidden", timeout: 90_000 });
    }
    await expect(page.locator('[data-testid="terminal-workspace-grid"]')).toHaveAttribute(
      "data-active-symbols",
      /BTC/,
      { timeout: 30_000 },
    );
    await expect(page.getByTestId("terminal-quote-last-BTC")).toBeVisible({ timeout: 90_000 });
    const terminalText = await page.getByTestId("terminal-quote-last-BTC").innerText();
    expect(terminalText.replace(/\s/g, "")).toMatch(/50,000\.125/);

    expect(todayText.replace(/\s/g, "")).toBe(terminalText.replace(/\s/g, ""));
  });
});
