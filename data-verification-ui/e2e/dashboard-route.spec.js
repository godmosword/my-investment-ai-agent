// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Dashboard route /dashboard (Queue 39)", () => {
  test("loads macro snapshot cards, catalysts, and BTC alignment strip", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });

    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("macro-indicator-grid")).toBeVisible();
    await expect(page.locator('article[data-testid^="macro-indicator-"]')).toHaveCount(8);
    await expect(page.getByTestId("macro-indicator-btc")).toContainText("BTC");
    await expect(page.getByTestId("macro-indicator-next_fed_cpi")).toContainText("US CPI");
    await expect(page.getByTestId("catalyst-calendar")).toContainText("US CPI");
    await expect(page.getByTestId("macro-regime-panel")).toContainText("RISK ON");
    await expect(page.getByTestId("macro-regime-badge")).toContainText("RISK ON");
    await expect(page.getByTestId("today-btc-quote-last")).toContainText(/50,000\.125/);
  });

  test("missing regime shows UNKNOWN, not NEUTRAL·0", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["zero_rate"],
          indicators: {
            zero_rate: {
              id: "zero_rate",
              label: "Zero Rate",
              value: 0,
              display: "0.00",
              unit: "%",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
              spark: [0, 0, 0],
              source: "e2e",
            },
          },
          catalysts: [],
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    const badge = page.getByTestId("macro-regime-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("UNKNOWN");
    await expect(badge).not.toContainText("NEUTRAL");
    await expect(badge).not.toContainText("0");
    await expect(page.getByTestId("macro-dashboard-loading")).toHaveCount(0);
    await expect(page.getByTestId("macro-dashboard-error")).toHaveCount(0);
  });

  test("production empty-drivers regime {neutral, 0, []} shows UNKNOWN, not NEUTRAL·0", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["zero_rate"],
          indicators: {
            zero_rate: {
              id: "zero_rate",
              label: "Zero Rate",
              value: 0,
              display: "0.00",
              unit: "%",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
              spark: [0, 0, 0],
              source: "e2e",
            },
          },
          catalysts: [],
          regime: { label: "neutral", score: 0, drivers: [] },
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    const badge = page.getByTestId("macro-regime-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("UNKNOWN");
    await expect(badge).not.toContainText("NEUTRAL");
    await expect(badge).not.toContainText("0");
  });

  test("real neutral with score 0 and a driver still shows NEUTRAL · 0", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["zero_rate"],
          indicators: {
            zero_rate: {
              id: "zero_rate",
              label: "Zero Rate",
              value: 0,
              display: "0.00",
              unit: "%",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
              spark: [0, 0, 0],
              source: "e2e",
            },
          },
          catalysts: [],
          regime: { label: "neutral", score: 0, drivers: [{ name: "VIX", score: 0, note: "20.0" }] },
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    const badge = page.getByTestId("macro-regime-badge");
    await expect(badge).toHaveText("NEUTRAL · 0");
    await expect(page.getByTestId("regime-driver-bar")).toBeVisible();
  });

  test("loaded empty indicator_order shows explicit empty, not a blank grid", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: [],
          indicators: {},
          catalysts: [],
          regime: { label: "neutral", score: 0, drivers: [] },
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("macro-dashboard-loading")).toHaveCount(0);
    await expect(page.getByTestId("macro-dashboard-error")).toHaveCount(0);
    await expect(page.getByTestId("macro-indicator-grid")).toHaveCount(0);
    const empty = page.getByTestId("macro-indicator-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("尚無宏觀指標");
    await expect(page.getByTestId("macro-regime-badge")).toHaveText("UNKNOWN");
  });

  test("indicator value 0 still renders a card, not empty", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["zero_rate"],
          indicators: {
            zero_rate: {
              id: "zero_rate",
              label: "Zero Rate",
              value: 0,
              display: "0.00",
              unit: "%",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
              spark: [0, 0, 0],
              source: "e2e",
            },
          },
          catalysts: [],
          regime: { label: "neutral", score: 0, drivers: [] },
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("macro-indicator-grid")).toBeVisible();
    await expect(page.getByTestId("macro-indicator-zero_rate")).toBeVisible();
    await expect(page.getByTestId("macro-indicator-empty")).toHaveCount(0);
  });

  test("macro error keeps error banner and does not show empty", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "macro snapshot failed" }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("macro-dashboard-error")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("macro-indicator-empty")).toHaveCount(0);
    await expect(page.getByTestId("macro-indicator-grid")).toHaveCount(0);
    const badge = page.getByTestId("macro-regime-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("UNKNOWN");
    await expect(badge).not.toContainText("NEUTRAL");
    await expect(badge).not.toContainText("0");
    await expect(page.getByTestId("macro-dashboard-loading")).toHaveCount(0);
  });

  test("driver missing score shows UNKNOWN, not a 0-neutral bar", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["zero_rate"],
          indicators: {
            zero_rate: {
              id: "zero_rate",
              label: "Zero Rate",
              value: 0,
              display: "0.00",
              unit: "%",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
              spark: [0, 0, 0],
              source: "e2e",
            },
          },
          catalysts: [],
          regime: {
            label: "risk_on",
            score: 1,
            drivers: [{ name: "VIX", note: "n/a" }],
          },
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    const panel = page.getByTestId("macro-regime-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("regime-driver-unknown")).toBeVisible();
    await expect(page.getByTestId("regime-driver-unknown")).toHaveCount(1);
    await expect(page.getByTestId("regime-driver-unknown")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("regime-driver-caption")).not.toContainText("UNKNOWN");
    await expect(page.getByTestId("regime-driver-bar")).toHaveCount(0);
    await expect(page.getByTestId("macro-regime-badge")).toContainText("RISK ON");
    await expect(panel).toContainText("VIX");
    const unknownMatches = (await panel.innerText()).match(/UNKNOWN/g) || [];
    expect(unknownMatches).toHaveLength(1);
  });

  test("catalyst missing importance shows UNKNOWN, not high", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["zero_rate"],
          indicators: {
            zero_rate: {
              id: "zero_rate",
              label: "Zero Rate",
              value: 0,
              display: "0.00",
              unit: "%",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
              spark: [0, 0, 0],
              source: "e2e",
            },
          },
          catalysts: [{ date: "2026-05-15", name: "US CPI" }],
          regime: { label: "neutral", score: 0, drivers: [] },
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    const calendar = page.getByTestId("catalyst-calendar");
    await expect(calendar).toBeVisible();
    await expect(calendar).toContainText("US CPI");
    const importance = calendar.getByTestId("catalyst-importance");
    await expect(importance).toHaveText("UNKNOWN");
    await expect(importance).not.toHaveText(/high/i);
  });

  test("catalyst missing date shows UNKNOWN, not TBD", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["zero_rate"],
          indicators: {
            zero_rate: {
              id: "zero_rate",
              label: "Zero Rate",
              value: 0,
              display: "0.00",
              unit: "%",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
              spark: [0, 0, 0],
              source: "e2e",
            },
          },
          catalysts: [
            { date: "2026-05-15", name: "US CPI", importance: "high" },
            { name: "Mystery event", importance: "high" },
          ],
          regime: { label: "neutral", score: 0, drivers: [] },
        }),
      });
    });
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("dashboard-home")).toBeVisible({ timeout: 60_000 });
    const calendar = page.getByTestId("catalyst-calendar");
    await expect(calendar).toBeVisible();
    const dates = calendar.getByTestId("catalyst-date");
    await expect(dates).toHaveCount(2);
    await expect(dates.nth(0)).toHaveText("2026-05-15");
    await expect(dates.nth(1)).toHaveText("UNKNOWN");
    await expect(calendar).toContainText("Mystery event");
    await expect(calendar).not.toContainText("TBD");
  });

});
