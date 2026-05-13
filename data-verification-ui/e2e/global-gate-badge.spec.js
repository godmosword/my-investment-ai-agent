// @ts-check
import { test, expect } from "@playwright/test";

/**
 * GlobalGateBadge — shows latest report's reviewer-loop verdict in the Command Bar
 * trailing slot. Hidden when /api/reports returns empty (mock-api-server default).
 */
test.describe("Global Gate Badge", () => {
  test("renders pass variant and links to /report/:date", async ({ page }) => {
    const reportDate = "2026-05-09";

    await page.route(/\/api\/reports\?/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { report_date: reportDate, href: `/report/${reportDate}`, api_href: `/api/reports/${reportDate}` },
        ]),
      });
    });
    await page.route(`**/api/reports/${reportDate}/gate-status`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          gate_status: "pass",
          run_id: "e2e-run",
          degraded: false,
          revision_count: 1,
          final_trade_count: 3,
        }),
      });
    });

    await page.goto("/insights", { waitUntil: "load" });

    const badge = page.getByTestId("global-gate-badge");
    await expect(badge).toBeVisible({ timeout: 60_000 });
    await expect(badge).toHaveAttribute("data-gate-status", "pass");
    await expect(badge).toHaveAttribute("href", `/report/${reportDate}`);
    await expect(badge).toContainText(reportDate);
    await expect(badge.getByTestId("gate-badge-pass")).toBeVisible();
    await expect(badge).toContainText("(1r)");
  });

  test("renders critical variant on fail", async ({ page }) => {
    const reportDate = "2026-05-08";

    await page.route(/\/api\/reports\?/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { report_date: reportDate, href: `/report/${reportDate}`, api_href: `/api/reports/${reportDate}` },
        ]),
      });
    });
    await page.route(`**/api/reports/${reportDate}/gate-status`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          gate_status: "fail",
          run_id: "e2e-run",
          degraded: true,
          revision_count: 2,
          final_trade_count: 0,
        }),
      });
    });

    await page.goto("/insights", { waitUntil: "load" });

    const badge = page.getByTestId("global-gate-badge");
    await expect(badge).toBeVisible({ timeout: 60_000 });
    await expect(badge).toHaveAttribute("data-gate-status", "fail");
    await expect(badge).toContainText(/FAIL/);
    await expect(badge.getByTestId("gate-badge-critical")).toBeVisible();
    await expect(badge).toContainText("(2r)");
  });

  test("hidden when no reports available", async ({ page }) => {
    // Default mock returns []; just navigate and assert hidden state.
    await page.goto("/insights", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("global-gate-badge")).toHaveCount(0);
  });
});
