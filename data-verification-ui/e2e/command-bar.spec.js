// @ts-check
import { test, expect } from "@playwright/test";

test.describe("FE-5 desktop power features — Cmd+K focus + G-chord shortcuts", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("Cmd+K focuses the terminal command bar input", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("terminal-command-bar")).toBeVisible({ timeout: 60_000 });

    await page.keyboard.press("Meta+K");
    const input = page.getByTestId("cmd-bar-input");
    await expect(input).toBeFocused();
  });

  test("command bar chrome is 指令列 / 指令 / 前往; GO text stays GO", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    const bar = page.getByTestId("terminal-command-bar");
    await expect(bar).toBeVisible({ timeout: 60_000 });
    await expect(bar).toHaveAttribute("aria-label", "指令列");
    await expect(page.getByTestId("cmd-bar-label")).toHaveText("指令");
    await expect(page.getByTestId("cmd-bar-input")).toHaveAttribute("aria-label", "指令輸入");
    const go = page.getByTestId("cmd-bar-go");
    await expect(go).toHaveText("GO");
    await expect(go).toHaveAttribute("aria-label", "前往");
    await expect(page.getByTestId("cmd-bar-watch")).toHaveText("觀察");
    await expect(bar).not.toHaveAttribute("aria-label", "Terminal Command Bar");
    await expect(page.getByTestId("cmd-bar-label")).not.toHaveText("Cmd");
  });

  test("G then B chord navigates to /insights", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("terminal-command-bar")).toBeVisible({ timeout: 60_000 });
    // Ensure focus is on body, not an input, so chord listener fires.
    await page.locator("body").click({ position: { x: 5, y: 5 } });

    await page.keyboard.press("KeyG");
    await page.keyboard.press("KeyB");
    await expect(page).toHaveURL(/\/insights(\?|$)/);
  });

  test("G then M chord navigates to Portfolio Monitor tab", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("terminal-command-bar")).toBeVisible({ timeout: 60_000 });
    await page.locator("body").click({ position: { x: 5, y: 5 } });

    await page.keyboard.press("KeyG");
    await page.keyboard.press("KeyM");
    await expect(page).toHaveURL(/\/portfolio\?tab=monitor/);
  });

  test("SideNav shortcut hint renders on desktop", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("side-nav-shortcut-hint")).toBeVisible({ timeout: 60_000 });
  });

  test("chord is suppressed while typing in an input", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "load" });
    await expect(page.getByTestId("terminal-command-bar")).toBeVisible({ timeout: 60_000 });

    const input = page.getByTestId("cmd-bar-input");
    await input.click();
    await input.fill("");
    await page.keyboard.type("GB");
    // Should still be on /dashboard, not navigated away.
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
