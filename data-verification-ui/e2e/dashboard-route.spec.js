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

  test("missing or non-finite indicator value shows UNKNOWN, not N/A", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["missing_val", "bad_val", "na_prod", "display_ok", "usd_ok"],
          indicators: {
            missing_val: {
              id: "missing_val",
              label: "Missing Val",
              source: "e2e",
            },
            bad_val: {
              id: "bad_val",
              label: "Bad Val",
              value: "n/a",
              source: "e2e",
            },
            na_prod: {
              id: "na_prod",
              label: "Next Fed / CPI",
              value: null,
              display: "N/A",
              unit: "days",
              change_1d: null,
              change_5d: null,
              change_unit: "days",
              spark: [],
              source: "financialmodelingprep_optional",
              as_of: "2026-05-13T00:00:00Z",
              error: "calendar_unavailable",
            },
            display_ok: {
              id: "display_ok",
              label: "Display Ok",
              value: 12.5,
              display: "12.5x",
              source: "e2e",
            },
            usd_ok: {
              id: "usd_ok",
              label: "USD Ok",
              value: 1234,
              unit: "USD",
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
    await expect(page.getByTestId("macro-indicator-missing_val").getByTestId("macro-indicator-value")).toHaveText(
      "UNKNOWN",
    );
    await expect(page.getByTestId("macro-indicator-bad_val").getByTestId("macro-indicator-value")).toHaveText(
      "UNKNOWN",
    );
    await expect(page.getByTestId("macro-indicator-na_prod").getByTestId("macro-indicator-value")).toHaveText(
      "UNKNOWN",
    );
    await expect(page.getByTestId("macro-indicator-display_ok").getByTestId("macro-indicator-value")).toHaveText(
      "12.5x",
    );
    await expect(page.getByTestId("macro-indicator-usd_ok").getByTestId("macro-indicator-value")).toHaveText(
      "$1,234",
    );
    await expect(page.getByTestId("macro-indicator-grid")).not.toContainText("N/A");
  });

  test("missing change shows UNKNOWN, not em dash; real 0 stays 0.00%", async ({ page }) => {
    await page.route("**/api/macro/snapshot", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          as_of: "2026-05-13T00:00:00Z",
          cached: false,
          indicator_order: ["missing_chg", "zero_chg"],
          indicators: {
            missing_chg: {
              id: "missing_chg",
              label: "Missing Chg",
              value: 10,
              display: "10.00",
              source: "e2e",
            },
            zero_chg: {
              id: "zero_chg",
              label: "Zero Chg",
              value: 0,
              display: "0.00",
              change_1d: 0,
              change_5d: 0,
              change_unit: "%",
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

    const missing = page.getByTestId("macro-indicator-missing_chg");
    await expect(missing.getByTestId("macro-indicator-change-5d")).toHaveText("5D UNKNOWN");
    await expect(missing.getByTestId("macro-indicator-change-1d")).toHaveText("1D UNKNOWN");
    await expect(missing).not.toContainText("—");

    const zero = page.getByTestId("macro-indicator-zero_chg");
    await expect(zero.getByTestId("macro-indicator-change-5d")).toHaveText("5D 0.00%");
    await expect(zero.getByTestId("macro-indicator-change-1d")).toHaveText("1D 0.00%");
    await expect(zero).not.toContainText("UNKNOWN");
    await expect(page.getByTestId("macro-indicator-grid")).not.toContainText("—");
  });

});
