// @ts-check
import { test, expect } from "@playwright/test";

test.describe("FE-1 Responsive App Shell", () => {
  test("mobile 375px shows BottomNav and hides SideNav", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/dashboard", { waitUntil: "load" });

    const bottomNav = page.locator("nav.bottom-nav");
    await expect(bottomNav).toBeVisible({ timeout: 60_000 });

    const sideNav = page.locator("nav.side-nav");
    await expect(sideNav).toBeHidden();
  });

  test("desktop 1280px shows SideNav and hides BottomNav", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/dashboard", { waitUntil: "load" });

    const sideNav = page.locator("nav.side-nav");
    await expect(sideNav).toBeVisible({ timeout: 60_000 });

    const bottomNav = page.locator("nav.bottom-nav");
    await expect(bottomNav).toBeHidden();
  });

  test("CSS variables --bottom-tab-height and --sidebar-width are defined", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    const vars = await page.evaluate(() => {
      const styles = getComputedStyle(document.documentElement);
      return {
        bottomTab: styles.getPropertyValue("--bottom-tab-height").trim(),
        sidebar: styles.getPropertyValue("--sidebar-width").trim(),
        navH: styles.getPropertyValue("--nav-h").trim(),
      };
    });
    expect(vars.navH).toBe("56px");
    expect(vars.bottomTab).not.toBe("");
    expect(vars.sidebar).toBe("220px");
  });
});
