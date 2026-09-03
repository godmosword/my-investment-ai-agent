// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Portfolio TP/SL calculator (queue 45 · P1)", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.removeItem("qsi_risk_budget_v1");
      } catch {
        /* ignore */
      }
    });
  });

  test("computes risk metrics from entry/stop/target", async ({ page }) => {
    await page.goto("/portfolio?tab=risk", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("risk-equity-input").fill("50000");
    await page.getByTestId("risk-pct-input").fill("1");
    await page.getByTestId("risk-symbol-input").fill("NVDA");
    await page.getByTestId("risk-entry-input").fill("100");
    await page.getByTestId("risk-stop-input").fill("95");
    await page.getByTestId("risk-target-input").fill("115");

    // Risk per share = 5, reward per share = 15 → R/R = 3.00
    await expect(page.getByTestId("risk-per-share")).toHaveText("5.00");
    await expect(page.getByTestId("reward-per-share")).toHaveText("15.00");
    await expect(page.getByTestId("risk-rr")).toHaveText("3.00");
    // Budget = 50000 × 1% = 500; shares = floor(500 / 5) = 100
    await expect(page.getByTestId("risk-position-shares")).toHaveText("100");
    // Notional = 100 × 100 = $10,000; risk $ = 100 × 5 = $500
    await expect(page.getByTestId("risk-notional")).toHaveText("$10,000");
    await expect(page.getByTestId("risk-actual-dollars")).toHaveText("$500");
  });

  test("flags LONG with stop above entry as invalid", async ({ page }) => {
    await page.goto("/portfolio?tab=risk", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("risk-equity-input").fill("10000");
    await page.getByTestId("risk-entry-input").fill("100");
    await page.getByTestId("risk-stop-input").fill("105");

    await expect(page.getByTestId("risk-issues")).toContainText("LONG: stop 需 < entry");
    await expect(page.getByTestId("risk-submit-intent")).toBeDisabled();
  });

  test("persists risk budget to localStorage", async ({ page, context }) => {
    await page.goto("/portfolio?tab=risk", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("risk-equity-input").fill("123456");
    await page.getByTestId("risk-pct-input").fill("0.75");

    const stored = await page.evaluate(() => window.localStorage.getItem("qsi_risk_budget_v1"));
    expect(stored).not.toBeNull();
    const parsed = JSON.parse(stored ?? "{}");
    expect(parsed.account_equity).toBe(123456);
    expect(parsed.risk_pct).toBe(0.75);
  });

  test("empty equity does not persist 0 and budget is UNKNOWN not $0", async ({ page }) => {
    await page.goto("/portfolio?tab=risk", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });

    const equity = page.getByTestId("risk-equity-input");
    const budget = page.getByTestId("risk-budget-value");
    await expect(equity).toHaveValue("");
    await expect(budget).toHaveText("UNKNOWN");
    await expect(budget).not.toHaveText("$0");

    await expect
      .poll(async () => {
        const raw = await page.evaluate(() => window.localStorage.getItem("qsi_risk_budget_v1"));
        if (!raw) return "missing";
        return JSON.parse(raw).account_equity;
      })
      .not.toBe(0);

    await equity.fill("50000");
    await expect(budget).toHaveText("$500");

    await equity.fill("");
    await expect(budget).toHaveText("UNKNOWN");
    await expect(budget).not.toHaveText("$0");
    await expect
      .poll(async () => {
        const raw = await page.evaluate(() => window.localStorage.getItem("qsi_risk_budget_v1"));
        if (!raw) return "missing";
        return JSON.parse(raw).account_equity;
      })
      .toBe("");

    await page.reload({ waitUntil: "load" });
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("risk-equity-input")).toHaveValue("");
    await expect(page.getByTestId("risk-budget-value")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("risk-budget-value")).not.toHaveText("$0");
  });

  test("submits manual PENDING_REVIEW intent on click", async ({ page }) => {
    await page.goto("/portfolio?tab=risk", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("risk-equity-input").fill("50000");
    await page.getByTestId("risk-pct-input").fill("1");
    await page.getByTestId("risk-symbol-input").fill("NVDA");
    await page.getByTestId("risk-entry-input").fill("100");
    await page.getByTestId("risk-stop-input").fill("95");
    await page.getByTestId("risk-target-input").fill("115");

    const submit = page.getByTestId("risk-submit-intent");
    await expect(submit).toBeEnabled();
    await submit.click();
    await expect(page.getByTestId("risk-submit-note")).toContainText("PENDING_REVIEW");
  });

  test("ATR14 helper fills stop based on mocked OHLC", async ({ page }) => {
    await page.goto("/portfolio?tab=risk", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-risk-panel")).toBeVisible({ timeout: 60_000 });

    await page.getByTestId("risk-symbol-input").fill("NVDA");
    await page.getByTestId("risk-entry-input").fill("100");

    const atrBtn = page.getByTestId("risk-apply-atr-stop");
    // Wait for analysis bundle to populate (mock returns immediately on next tick).
    await expect(atrBtn).toBeEnabled({ timeout: 10_000 });
    await atrBtn.click();
    // ATR14 ≈ 2.0 (mocked bars: high-low spread = 2). LONG stop ≈ 100 - 2 = 98.00
    await expect(page.getByTestId("risk-stop-input")).toHaveValue("98.00");
  });
});
