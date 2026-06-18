// @ts-check
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4173";
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  workers: 1,
  ...(isCI
    ? {
        globalTimeout: 25 * 60 * 1000,
        maxFailures: 8,
      }
    : {}),
  reporter: isCI
    ? [
        ["github"],
        ["html", { open: "never", outputFolder: "playwright-report" }],
        ["junit", { outputFile: "e2e-results/junit.xml" }],
      ]
    : "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
