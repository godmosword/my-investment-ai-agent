import { test, expect } from "@playwright/test";

function isScenarioPath(pathname) {
  return pathname === "/api/scenario/suggestions" || pathname === "/api/scenario/suggestions/";
}

function scenarioPayload(overrides = {}) {
  return {
    enabled: true,
    as_of: "2026-05-14T00:00:00Z",
    disclaimer: "e2e mock; internal planning only.",
    portfolio: { positions: 1, concentration_hhi: 1, top_symbols: [{ symbol: "NVDA", weight_pct: 100 }] },
    scenarios: [
      { id: "defensive", label: "Defensive tilt", notional_shift_pct: -5, notes: "mock" },
      { id: "base", label: "Hold structure", notional_shift_pct: 0, notes: "mock" },
    ],
    target_hints: [],
    ...overrides,
  };
}

test.describe("Insights scenario tab (queue 28d UI)", () => {
  test("shows scenario cards from mock API", async ({ page }) => {
    await page.goto("/insights?tab=scenario");
    await expect(page.getByTestId("insights-tab-scenario")).toBeVisible();
    await expect(page.getByTestId("scenario-planner-home")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("scenario-card-defensive")).toBeVisible();
    await expect(page.getByTestId("scenario-card-base")).toBeVisible();
  });

  test("portfolio block is 持倉; empty top_symbols and missing HHI are UNKNOWN; finite 0 stays 0", async ({ page }) => {
    await page.goto("/insights?tab=scenario");
    await expect(page.getByTestId("scenario-planner-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("scenario-portfolio-title")).toHaveText("持倉");
    await expect(page.getByTestId("scenario-portfolio-title")).not.toHaveText("Portfolio");
    await expect(page.getByTestId("scenario-hhi")).toHaveText("1");
    await expect(page.getByTestId("scenario-top-symbols")).toContainText("NVDA 100%");
    await expect(page.getByTestId("scenario-portfolio")).not.toContainText("Portfolio");

    await page.route(
      (url) => isScenarioPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            scenarioPayload({
              portfolio: { positions: 0, concentration_hhi: null, top_symbols: [] },
            }),
          ),
        });
      },
    );
    await page.reload({ waitUntil: "load" });
    await expect(page.getByTestId("scenario-planner-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("scenario-portfolio-title")).toHaveText("持倉");
    await expect(page.getByTestId("scenario-hhi")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("scenario-top-symbols")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("scenario-hhi")).not.toHaveText("—");
    await expect(page.getByTestId("scenario-top-symbols")).not.toHaveText("—");
  });

  test("non-finite HHI is UNKNOWN; real HHI 0 stays 0", async ({ page }) => {
    await page.route(
      (url) => isScenarioPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            scenarioPayload({
              portfolio: { positions: 0, concentration_hhi: "n/a", top_symbols: [{ symbol: "CASH", weight_pct: 0 }] },
            }),
          ),
        });
      },
    );
    await page.goto("/insights?tab=scenario", { waitUntil: "load" });
    await expect(page.getByTestId("scenario-planner-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("scenario-hhi")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("scenario-top-symbols")).toContainText("CASH 0%");

    await page.unroute((url) => isScenarioPath(url.pathname));
    await page.route(
      (url) => isScenarioPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(
            scenarioPayload({
              portfolio: { positions: 0, concentration_hhi: 0, top_symbols: [{ symbol: "CASH", weight_pct: 0 }] },
            }),
          ),
        });
      },
    );
    await page.reload({ waitUntil: "load" });
    await expect(page.getByTestId("scenario-planner-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("scenario-hhi")).toHaveText("0");
    await expect(page.getByTestId("scenario-hhi")).not.toHaveText("UNKNOWN");
  });
});
