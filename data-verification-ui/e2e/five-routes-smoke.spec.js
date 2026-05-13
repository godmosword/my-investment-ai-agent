// @ts-check
import { test, expect } from "@playwright/test";

const ROUTES = [
  { path: "/news", testId: "news-home", nav: "科技即時報" },
  { path: "/dashboard", testId: "dashboard-home", nav: "數據儀表板" },
  { path: "/insights", testId: "insights-home", nav: "投資觀點" },
  { path: "/columns", testId: "columns-home", nav: "科技專欄" },
  { path: "/portfolio", testId: "portfolio-home", nav: "Portfolio" },
];

test.describe("5-board Terminal routes", () => {
  for (const route of ROUTES) {
    test(`${route.path} renders Shell and board surface`, async ({ page }) => {
      await page.goto(route.path, { waitUntil: "load" });
      await expect(page.getByTestId(route.testId)).toBeVisible({ timeout: 60_000 });
      await expect(page.getByTestId("terminal-command-bar")).toBeVisible({ timeout: 60_000 });
      await expect(page.getByRole("link", { name: route.nav }).first()).toBeVisible();
    });
  }
});
