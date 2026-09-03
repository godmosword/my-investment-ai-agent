// @ts-check
import { test, expect } from "@playwright/test";

function isComputeMemoryPath(pathname) {
  return pathname === "/api/macro/compute-memory" || pathname === "/api/macro/compute-memory/";
}

test.describe("Dashboard — 算力／記憶體 mock panel (queue 45 · P2-mock)", () => {
  test("not-live mock shows UNKNOWN header badge and UNKNOWN cells, not fake HBM dollars", async ({ page }) => {
    // 44b: compute-memory now lives under the 市場深度 tab.
    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("compute-memory-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("compute-memory-disclaimer")).toContainText("MOCK FIXTURE");
    const headerBadge = panel.getByTestId("compute-memory-source-badge");
    await expect(headerBadge).toHaveText(/unknown/i);
    await expect(headerBadge).not.toHaveText(/mock/i);
    await expect(
      page.getByTestId("compute-memory-hbm-dram").getByTestId("compute-memory-block-source-badge"),
    ).toHaveText(/mock/i);

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

  test("not-live payload without source uses UNKNOWN, not mock", async ({ page }) => {
    await page.route(
      (url) => isComputeMemoryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            enabled: true,
            live: false,
            as_of: "2026-05-16",
            disclaimer: "e2e missing source — not a live feed",
            hbm_dram_spot: { items: [] },
            hyperscaler_capex: { items: [] },
            gpu_spot: { items: [] },
          }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("compute-memory-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });

    const headerBadge = panel.getByTestId("compute-memory-source-badge");
    await expect(headerBadge).toHaveText(/unknown/i);
    await expect(headerBadge).not.toHaveText(/mock/i);

    const blockBadge = page
      .getByTestId("compute-memory-hbm-dram")
      .getByTestId("compute-memory-block-source-badge");
    await expect(blockBadge).toHaveText(/unknown/i);
    await expect(blockBadge).not.toHaveText(/mock/i);
  });

  test("live header badge stays live", async ({ page }) => {
    await page.route(
      (url) => isComputeMemoryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            enabled: true,
            live: true,
            source: "sec_edgar",
            as_of: "2026-05-16",
            disclaimer: "LIVE e2e",
            hbm_dram_spot: { source: "sec_edgar", items: [] },
            hyperscaler_capex: { items: [] },
            gpu_spot: { items: [] },
          }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("compute-memory-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    await expect(panel.getByTestId("compute-memory-source-badge")).toHaveText(/live/i);
  });

  test("present source string still shows when not live", async ({ page }) => {
    await page.route(
      (url) => isComputeMemoryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            enabled: true,
            live: false,
            source: "sec_edgar",
            as_of: "2026-05-16",
            disclaimer: "not live; named source",
            hbm_dram_spot: { source: "sec_edgar", items: [] },
            hyperscaler_capex: { items: [] },
            gpu_spot: { items: [] },
          }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const panel = page.getByTestId("compute-memory-panel");
    await expect(panel).toBeVisible({ timeout: 60_000 });
    const headerBadge = panel.getByTestId("compute-memory-source-badge");
    await expect(headerBadge).toHaveText(/sec_edgar/i);
    await expect(headerBadge).not.toHaveText(/mock/i);
    await expect(headerBadge).not.toHaveText(/unknown/i);
    await expect(
      page.getByTestId("compute-memory-hbm-dram").getByTestId("compute-memory-block-source-badge"),
    ).toHaveText(/sec_edgar/i);
  });
});

