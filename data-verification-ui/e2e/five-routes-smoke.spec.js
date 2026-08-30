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
      const workbenchIntroId = {
        "/insights": "insights-workbench-intro",
        "/portfolio": "portfolio-workbench-intro",
        "/dashboard": "dashboard-workbench-intro",
      }[route.path];
      if (workbenchIntroId) {
        await page.getByTestId(workbenchIntroId).evaluate((el) => {
          if (el instanceof HTMLDetailsElement) el.open = true;
        });
      }
      await expect(page.getByTestId(route.provenance).first()).toBeVisible({ timeout: 60_000 });
    });
  }

  test("/insights shows cross-tab data health summary", async ({ page }) => {
    await page.goto("/insights", { waitUntil: "load" });
    await expect(page.getByTestId("insights-home")).toBeVisible({ timeout: 60_000 });
    await page.getByTestId("insights-workbench-intro").evaluate((el) => {
      if (el instanceof HTMLDetailsElement) el.open = true;
    });
    const panel = page.getByTestId("insights-data-health-summary");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel).toContainText("Options");
    await expect(panel).toContainText("Track Record");
  });

  test("320px BottomNav six tabs stay single-line without overlap", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 568 });
    await page.goto("/news", { waitUntil: "load" });
    const nav = page.locator("nav.bottom-nav");
    await expect(nav).toBeVisible({ timeout: 60_000 });
    const items = nav.locator("a.nav-item");
    await expect(items).toHaveCount(6);

    const expected = [
      { href: "/news", name: "科技即時報" },
      { href: "/dashboard", name: "數據儀表板" },
      { href: "/insights", name: "投資觀點" },
      { href: "/columns", name: "科技專欄" },
      { href: "/portfolio", name: "Portfolio" },
      { href: "/settings", name: "設定" },
    ];
    for (let i = 0; i < expected.length; i++) {
      const item = items.nth(i);
      await expect(item).toHaveAttribute("aria-label", expected[i].name);
      await expect(item).toHaveAttribute("href", expected[i].href);
    }

    const metrics = await nav.evaluate((el) => {
      const navRect = el.getBoundingClientRect();
      const tabs = [...el.querySelectorAll("a.nav-item")].map((tab) => {
        const r = tab.getBoundingClientRect();
        const label = tab.querySelector(".nav-item__label");
        return {
          left: r.left,
          right: r.right,
          height: r.height,
          overflowX: tab.scrollWidth - tab.clientWidth,
          overflowY: tab.scrollHeight - tab.clientHeight,
          labelLines: label ? label.getClientRects().length : 0,
        };
      });
      return { navHeight: navRect.height, navWidth: navRect.width, tabs };
    });

    expect(metrics.navHeight).toBeLessThanOrEqual(56);
    expect(metrics.navWidth).toBeLessThanOrEqual(320);
    for (const tab of metrics.tabs) {
      expect(tab.height).toBeLessThanOrEqual(56);
      expect(tab.overflowX).toBeLessThanOrEqual(1);
      expect(tab.overflowY).toBeLessThanOrEqual(1);
      expect(tab.labelLines).toBe(1);
    }
    for (let i = 0; i < metrics.tabs.length - 1; i++) {
      expect(metrics.tabs[i + 1].left).toBeGreaterThanOrEqual(metrics.tabs[i].right - 0.5);
    }
  });

});
