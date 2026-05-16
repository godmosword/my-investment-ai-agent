// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Dashboard — 算力／記憶體 mock panel (queue 45 · P2-mock)", () => {
  test("renders three blocks with mock badge and disclaimer", async ({ page }) => {
    // 44b: compute-memory now lives under the 市場深度 tab.
    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("compute-memory-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("compute-memory-disclaimer")).toContainText("MOCK FIXTURE");
    await expect(panel.getByTestId("compute-memory-source-badge").first()).toContainText(
      /mock/i,
    );

    const hbm = page.getByTestId("compute-memory-hbm-dram");
    await expect(hbm).toBeVisible();
    await expect(hbm.getByText("HBM3", { exact: true })).toBeVisible();
    await expect(hbm.getByText("HBM3e", { exact: true })).toBeVisible();

    const capex = page.getByTestId("compute-memory-capex");
    await expect(capex.getByText("MSFT", { exact: true })).toBeVisible();
    await expect(capex.getByText("META", { exact: true })).toBeVisible();

    const gpu = page.getByTestId("compute-memory-gpu-spot");
    await expect(gpu.getByText("H100 SXM", { exact: true })).toBeVisible();
    await expect(gpu.getByText("H200 SXM", { exact: true })).toBeVisible();
  });
});
