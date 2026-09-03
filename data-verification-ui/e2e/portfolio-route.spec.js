// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Portfolio route (/portfolio)", () => {
  test("loads holdings, KPIs, and tracker actions", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });

    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("portfolio-source-badge")).toContainText("jsonl");
    const totalValue = page.getByTestId("portfolio-total-value");
    await expect(totalValue).toContainText("$8,000");
    await expect(totalValue).not.toContainText("UNKNOWN");
    await expect(page.getByTestId("portfolio-day-pnl")).toContainText("+$120");
    await expect(page.getByTestId("portfolio-total-pnl")).toContainText("+$3,000");
    await expect(page.getByTestId("portfolio-holdings-table").getByTestId("portfolio-holding-symbol")).toHaveText("NVDA");
    await expect(page.getByTestId("portfolio-add-button")).toBeVisible();
    await expect(page.getByTestId("portfolio-import-button")).toBeVisible();
  });

  test("allocation donut renders slices from holdings (VU2)", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const donut = page.getByTestId("allocation-donut");
    await expect(donut).toBeVisible();
    await expect(donut.locator('[data-symbol="NVDA"]')).toBeVisible();
    await expect(page.getByTestId("allocation-slice").first()).toBeVisible();
  });

  test("holding symbol links to insights and news", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const table = page.getByTestId("portfolio-holdings-table");
    await expect(table.getByTestId("portfolio-holding-to-insights")).toHaveAttribute(
      "href",
      "/insights?symbol=NVDA",
    );
    await expect(table.getByTestId("portfolio-holding-to-news")).toHaveAttribute(
      "href",
      "/news?focus=NVDA",
    );
  });

  test("concentration shows highest-weight holding; cash is UNKNOWN", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const concentration = page.getByTestId("portfolio-concentration");
    await expect(concentration).toContainText("NVDA");
    await expect(concentration).toContainText("100");
    await expect(concentration).not.toContainText("產業");
    await expect(concentration).not.toContainText("地理");

    const cash = page.getByTestId("portfolio-cash-unknown");
    await expect(cash).toContainText("UNKNOWN");
    await expect(cash).toContainText("現金");
  });

  test("non-finite KPI totals show UNKNOWN, not invented $0", async ({ page }) => {
    await page.route("**/api/portfolio/pnl**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_value: "N/A",
          total_pnl: "missing",
          total_day_pnl: null,
          holdings: [
            {
              id: "1",
              symbol: "NVDA",
              shares: 10,
              cost_basis: 500,
              opened_at: "2024-01-01",
              notes: "",
              last_price: 800,
              day_change_pct: 1.5,
              market_value: 8000,
              cost: 5000,
              pnl: 3000,
              pnl_pct: 60,
              day_pnl: 120,
              weight: 100,
            },
          ],
        }),
      });
    });

    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    for (const [testId, label] of [
      ["portfolio-total-value", "總市值"],
      ["portfolio-day-pnl", "今日損益"],
      ["portfolio-total-pnl", "總損益"],
    ]) {
      const card = page.getByTestId(testId);
      await expect(card).toContainText(label);
      await expect(card).toContainText("UNKNOWN");
      await expect(card).not.toContainText("$0");
    }
    await expect(page.getByTestId("portfolio-day-pnl-sub")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("portfolio-total-pnl-sub")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("portfolio-day-pnl-sub")).not.toContainText("+0.0%");
    await expect(page.getByTestId("portfolio-total-pnl-sub")).not.toContainText("+0.0%");
    await expect(page.getByTestId("portfolio-day-pnl-sub")).not.toContainText("0.0%");
    await expect(page.getByTestId("portfolio-total-pnl-sub")).not.toContainText("0.0%");
  });

  test("production pnl zeros with quote_unavailable holding show UNKNOWN, not $0", async ({ page }) => {
    await page.route("**/api/portfolio/pnl**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          enabled: true,
          source: "jsonl",
          as_of: "2026-06-26T00:00:00Z",
          total_value: 0,
          total_pnl: 0,
          total_day_pnl: 0,
          holdings: [
            {
              id: "1",
              symbol: "NVDA",
              shares: 10,
              cost_basis: 500,
              opened_at: "2024-01-01",
              notes: "",
              error: "quote_unavailable",
            },
          ],
        }),
      });
    });

    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    for (const [testId, label] of [
      ["portfolio-total-value", "總市值"],
      ["portfolio-day-pnl", "今日損益"],
      ["portfolio-total-pnl", "總損益"],
    ]) {
      const card = page.getByTestId(testId);
      await expect(card).toContainText(label);
      await expect(card).toContainText("UNKNOWN");
      await expect(card).not.toContainText("$0");
    }
    await expect(page.getByTestId("portfolio-day-pnl-sub")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("portfolio-total-pnl-sub")).toHaveText("UNKNOWN");
    await expect(page.getByTestId("portfolio-day-pnl-sub")).not.toContainText("+0.0%");
    await expect(page.getByTestId("portfolio-total-pnl-sub")).not.toContainText("+0.0%");
    await expect(page.getByTestId("portfolio-day-pnl-sub")).not.toContainText("0.0%");
    await expect(page.getByTestId("portfolio-total-pnl-sub")).not.toContainText("0.0%");
  });

  test("holding insight and news links are at least 36px tall on table and cards", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    const table = page.getByTestId("portfolio-holdings-table");
    for (const testId of ["portfolio-holding-to-insights", "portfolio-holding-to-news"]) {
      const box = await table.getByTestId(testId).boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(36);
    }
    await page.setViewportSize({ width: 375, height: 812 });
    const card = page.getByTestId("portfolio-holding-card-NVDA");
    await expect(card).toBeVisible();
    for (const testId of ["portfolio-holding-to-insights", "portfolio-holding-to-news"]) {
      const box = await card.getByTestId(testId).boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(36);
    }
  });

  test("add-holding modal close has accessible name and is at least 36px tall", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("portfolio-add-button").click();
    const close = page.getByTestId("portfolio-add-modal-close");
    await expect(close).toBeVisible();
    await expect(close).toHaveAttribute("aria-label", "關閉");
    await expect(page.getByRole("button", { name: "關閉" })).toBeVisible();
    expect((await close.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(36);
  });

  test("holding delete buttons are at least 36px tall on table and cards", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    const tableDelete = page.getByTestId("portfolio-holdings-table").getByTestId("portfolio-holding-delete");
    await expect(tableDelete).toBeVisible();
    expect((await tableDelete.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(36);

    await page.setViewportSize({ width: 390, height: 844 });
    const cardDelete = page.getByTestId("portfolio-holding-card-NVDA").getByTestId("portfolio-holding-delete");
    await expect(cardDelete).toBeVisible();
    expect((await cardDelete.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(36);
  });

  test("matched holding shows D-n from upcoming earnings", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const table = page.getByTestId("portfolio-holdings-table");
    await expect(table.getByTestId("portfolio-holding-earnings-dn")).toHaveText("D-4");
  });

  test("expired and missing earnings days show UNKNOWN, not clamped D-0", async ({ page }) => {
    await page.route(
      (url) => url.pathname === "/api/earnings/upcoming" || url.pathname === "/api/earnings/upcoming/",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            as_of: "2026-05-16",
            days: 14,
            watchlist_size: 2,
            items: [
              {
                symbol: "NVDA",
                pillar: "ai_silicon",
                next_earnings_date: "2026-05-10",
                days_until: -6,
                status: "unknown",
              },
              {
                symbol: "AMD",
                pillar: "semiconductor",
                next_earnings_date: "2026-06-01",
                status: "unknown",
              },
            ],
          }),
        });
      },
    );

    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const table = page.getByTestId("portfolio-holdings-table");
    const dn = table.getByTestId("portfolio-holding-earnings-dn");
    await expect(dn).toHaveText("UNKNOWN");
    await expect(dn).not.toHaveText("D-0");
    await expect(table).not.toContainText("D-0");
    await expect(table).not.toContainText("D--6");
  });

  test("days_until 0 still shows D-0; unmatched holding is UNKNOWN", async ({ page }) => {
    await page.route("**/api/portfolio/pnl**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          total_value: 8000,
          total_pnl: 3000,
          total_day_pnl: 120,
          holdings: [
            {
              id: "1",
              symbol: "NVDA",
              shares: 10,
              cost_basis: 500,
              opened_at: "2024-01-01",
              notes: "",
              last_price: 800,
              day_change_pct: 1.5,
              market_value: 8000,
              cost: 5000,
              pnl: 3000,
              pnl_pct: 60,
              day_pnl: 120,
              weight: 50,
            },
            {
              id: "2",
              symbol: "AMD",
              shares: 5,
              cost_basis: 100,
              opened_at: "2024-02-01",
              notes: "",
              last_price: 120,
              day_change_pct: 0,
              market_value: 600,
              cost: 500,
              pnl: 100,
              pnl_pct: 20,
              day_pnl: 0,
              weight: 50,
            },
          ],
        }),
      });
    });
    await page.route(
      (url) => url.pathname === "/api/earnings/upcoming" || url.pathname === "/api/earnings/upcoming/",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            as_of: "2026-05-16",
            days: 14,
            watchlist_size: 1,
            items: [
              {
                symbol: "NVDA",
                pillar: "ai_silicon",
                next_earnings_date: "2026-05-16",
                days_until: 0,
                status: "unknown",
              },
            ],
          }),
        });
      },
    );

    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const table = page.getByTestId("portfolio-holdings-table");
    const rows = table.locator("tbody tr");
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0).getByTestId("portfolio-holding-earnings-dn")).toHaveText("D-0");
    await expect(rows.nth(1).getByTestId("portfolio-holding-earnings-dn")).toHaveText("UNKNOWN");
    await expect(rows.nth(1)).not.toContainText("D-0");
  });
});
