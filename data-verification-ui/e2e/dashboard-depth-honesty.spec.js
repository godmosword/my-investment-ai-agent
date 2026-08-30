// @ts-check
import { test, expect } from "@playwright/test";

function isComputeMemoryPath(pathname) {
  return pathname === "/api/macro/compute-memory" || pathname === "/api/macro/compute-memory/";
}

function isOnchainPath(pathname) {
  return pathname === "/api/macro/onchain" || pathname === "/api/macro/onchain/";
}

const LIVE_COMPUTE = {
  enabled: true,
  live: true,
  as_of: "2026-05-16",
  disclaimer: "LIVE e2e — real items.",
  hbm_dram_spot: {
    as_of: "2026-05-16",
    source: "e2e-live",
    note: "spot",
    items: [{ product: "HBM3", spec: "8H 16Gb", spot_usd: 9.2, trend_pct: 1.2 }],
  },
  hyperscaler_capex: { as_of: "2026-Q1", source: "e2e-live", items: [] },
  gpu_spot: { as_of: "2026-05-16", source: "e2e-live", items: [] },
};

const LIVE_ONCHAIN = {
  enabled: true,
  live: true,
  as_of: "2026-05-16",
  disclaimer: "LIVE e2e — real items.",
  btc_valuation: {
    as_of: "2026-05-16",
    source: "e2e-live",
    items: [
      { metric: "MVRV-Z", value: 1.85, regime: "neutral" },
      { metric: "Realized Price", value: 38500, unit: "USD" },
    ],
  },
  exchange_flow: { enabled: false, source: "none", reason: "no_free_equivalent", items: [] },
  funding_rate: { as_of: "2026-05-16", source: "e2e-live", items: [] },
};

test.describe("Dashboard depth — HBM / BTC valuation honesty (ITER-V2-012)", () => {
  test("default mock / not-live payload does not paint fake HBM or BTC dollars", async ({ page }) => {
    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });

    const compute = page.getByTestId("compute-memory-panel");
    await expect(compute).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("compute-memory-hbm-dram-empty")).toBeVisible();
    await expect(page.getByTestId("compute-memory-hbm-dram-empty")).toContainText("UNKNOWN：尚無真實資料");
    await expect(compute).not.toContainText("$9.20");
    await expect(compute).not.toContainText("$14.75");
    await expect(compute).not.toContainText("$2.49");
    await expect(compute).not.toContainText("HBM3e");
    await expect(compute).not.toContainText("fixture");
    await expect(compute).not.toContainText("compute_memory_mock.json");

    const onchain = page.getByTestId("onchain-panel");
    await expect(onchain).toBeVisible();
    await expect(page.getByTestId("onchain-btc-valuation-empty")).toBeVisible();
    await expect(page.getByTestId("onchain-btc-valuation-empty")).toContainText("UNKNOWN：尚無真實資料");
    await expect(onchain).not.toContainText("$38,500");
    await expect(onchain).not.toContainText("$64,200");
    await expect(onchain).not.toContainText("MVRV-Z");
    await expect(onchain).not.toContainText("fixture");
    await expect(onchain).not.toContainText("onchain_metrics_mock.json");
  });

  test("compute-memory loading / error / empty stay distinguishable", async ({ page }) => {
    let release;
    const gate = new Promise((resolve) => {
      release = resolve;
    });
    await page.route(
      (url) => isComputeMemoryPath(url.pathname),
      async (route) => {
        await gate;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ enabled: true, live: false, hbm_dram_spot: { items: [] } }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    await expect(page.getByTestId("compute-memory-loading")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("compute-memory-error")).toHaveCount(0);
    release();
    await expect(page.getByTestId("compute-memory-hbm-dram-empty")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId("compute-memory-loading")).toHaveCount(0);
    await expect(page.getByTestId("compute-memory-error")).toHaveCount(0);
  });

  test("compute-memory 500 shows error, not UNKNOWN empty", async ({ page }) => {
    await page.route(
      (url) => isComputeMemoryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "e2e compute-memory fail" }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const err = page.getByTestId("compute-memory-error");
    await expect(err).toBeVisible({ timeout: 60_000 });
    await expect(err).toContainText("無法載入算力／記憶體");
    await expect(page.getByTestId("compute-memory-hbm-dram-empty")).toHaveCount(0);
    await expect(page.getByTestId("compute-memory-loading")).toHaveCount(0);
  });

  test("onchain 500 shows error, not UNKNOWN empty", async ({ page }) => {
    await page.route(
      (url) => isOnchainPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "e2e onchain fail" }),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });
    const err = page.getByTestId("onchain-error");
    await expect(err).toBeVisible({ timeout: 60_000 });
    await expect(err).toContainText("無法載入 on-chain");
    await expect(page.getByTestId("onchain-btc-valuation-empty")).toHaveCount(0);
  });

  test("live payload still lists real HBM and BTC items", async ({ page }) => {
    await page.route(
      (url) => isComputeMemoryPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(LIVE_COMPUTE),
        });
      },
    );
    await page.route(
      (url) => isOnchainPath(url.pathname),
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(LIVE_ONCHAIN),
        });
      },
    );

    await page.goto("/dashboard?tab=depth", { waitUntil: "load" });

    const hbm = page.getByTestId("compute-memory-hbm-dram");
    await expect(hbm).toBeVisible({ timeout: 60_000 });
    await expect(hbm.getByText("HBM3", { exact: true })).toBeVisible();
    await expect(hbm).toContainText("$9.20");
    await expect(page.getByTestId("compute-memory-hbm-dram-empty")).toHaveCount(0);

    const valuation = page.getByTestId("onchain-btc-valuation");
    await expect(valuation.getByText("MVRV-Z", { exact: true })).toBeVisible();
    await expect(valuation).toContainText("$38,500");
    await expect(page.getByTestId("onchain-btc-valuation-empty")).toHaveCount(0);
  });
});
