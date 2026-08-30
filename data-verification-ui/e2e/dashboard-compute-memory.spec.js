// @ts-check
import { test, expect } from "@playwright/test";

test.describe("Dashboard — 算力／記憶體 mock panel (queue 45 · P2-mock)", () => {
  test("not-live mock shows badge and UNKNOWN, not fake HBM dollars", async ({ page }) => {
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
    await expect(page.getByTestId("compute-memory-hbm-dram-empty")).toContainText("UNKNOWN：尚無真實資料");
    await expect(hbm).not.toContainText("HBM3e");
    await expect(hbm).not.toContainText("$9.20");

    const capex = page.getByTestId("compute-memory-capex");
    await expect(page.getByTestId("compute-memory-capex-empty")).toContainText("UNKNOWN：尚無真實資料");
    await expect(capex).not.toContainText("MSFT");
    await expect(capex).not.toContainText("$22.4");

    const gpu = page.getByTestId("compute-memory-gpu-spot");
    await expect(page.getByTestId("compute-memory-gpu-spot-empty")).toContainText("UNKNOWN：尚無真實資料");
    await expect(gpu).not.toContainText("H100 SXM");
    await expect(gpu).not.toContainText("$2.49");
  });
});
