import { test, expect } from "@playwright/test";

test.describe("Queue 36 — module smoke (Analysis / Quant / Industries / Archive)", () => {
  test("AnalysisHome shows QSREC KPI row from mock qsrec-stats", async ({ page }) => {
    await page.goto("/analysis");
    await expect(page.getByText("投資分析")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("analysis-qsrec-kpis")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("通過率")).toBeVisible();
    await expect(page.getByText("80%")).toBeVisible();
  });

  test("QuantHome (Insights tab signals) shows gate badges and quant signals", async ({ page }) => {
    await page.goto("/insights?tab=signals");
    await expect(page.getByTestId("quant-m7-signals")).toBeVisible({ timeout: 30_000 });
    const gatePanel = page.getByTestId("quant-qsrec-gate-panel");
    await expect(gatePanel).toBeVisible();
    await expect(gatePanel.getByText("2026-05-09")).toBeVisible({ timeout: 30_000 });
    await expect(gatePanel.getByText("通過").first()).toBeVisible();
    await expect(gatePanel.getByText("需修正").first()).toBeVisible();
    await expect(gatePanel.getByText("降級").first()).toBeVisible();
  });

  test("IndustriesHome renders industry_trends blocks from structured mock", async ({ page }) => {
    await page.goto("/industries");
    await expect(page.getByText("產業趨勢")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("industries-brief-layouts-hint")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("industries-brief-layouts-hint")).toContainText("example_lite_reorder");
    await expect(page.getByText("2026-05-09").first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/mock sector view|industry_trends/i).first()).toBeVisible();
  });

  test("Archive profile picker sets profile=lite and localStorage", async ({ page }) => {
    await page.goto("/archive");
    await expect(page.getByText("報告存檔")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("profile-card-picker")).toBeVisible();
    await page.getByTestId("profile-card-picker").getByRole("button", { name: /Lite/i }).click();
    await expect(page).toHaveURL(/profile=lite/);
    const stored = await page.evaluate(() => localStorage.getItem("qsi_report_profile"));
    expect(stored).toBe("lite");
  });
});
