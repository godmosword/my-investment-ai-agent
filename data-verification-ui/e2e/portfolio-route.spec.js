// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Portfolio route (/portfolio)", () => {
  test("loads holdings, KPIs, and tracker actions", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });

    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("portfolio-source-badge")).toContainText("jsonl");
    await expect(page.getByTestId("portfolio-total-value")).toContainText("$8,000");
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

  test("matched holding shows D-n from upcoming earnings", async ({ page }) => {
    await page.goto("/portfolio", { waitUntil: "load" });
    await expect(page.getByTestId("portfolio-home")).toBeVisible({ timeout: 60_000 });

    const table = page.getByTestId("portfolio-holdings-table");
    await expect(table.getByTestId("portfolio-holding-earnings-dn")).toHaveText("D-4");
  });
});
