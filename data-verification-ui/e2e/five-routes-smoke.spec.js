// @ts-check
import { test, expect } from "@playwright/test";

const ROUTES = [
  { path: "/news", testId: "news-home", nav: "科技即時報", provenance: "reader-source-line" },
  { path: "/dashboard", testId: "dashboard-home", nav: "數據儀表板", provenance: "workbench-data-health-chip" },
  { path: "/insights", testId: "insights-home", nav: "投資觀點", provenance: "workbench-data-health-chip" },
  { path: "/columns", testId: "columns-home", nav: "科技專欄", provenance: "reader-source-line" },
  { path: "/portfolio", testId: "portfolio-home", nav: "Portfolio", provenance: "workbench-data-health-chip" },
];

test.describe("5-board Terminal routes", () => {
  for (const route of ROUTES) {
    test(`${route.path} renders Shell and board surface`, async ({ page }) => {
      await page.goto(route.path, { waitUntil: "load" });
      await expect(page.getByTestId(route.testId)).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("terminal-command-bar")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByRole("link", { name: route.nav }).first()).toBeVisible();
      await expect(page.getByTestId(route.provenance).first()).toBeVisible({ timeout: 60_000 });
    });
  }
});
