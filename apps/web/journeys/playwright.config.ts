import { defineConfig, devices } from "@playwright/test";

/**
 * Lane G's journey suite (see `lib.ts`). Separate from `e2e/`, so `make e2e` and the gates job do not run it; the
 * journeys workflow does (`.github/workflows/journeys.yml`). Locally, against a stack with the 1% Club seed:
 *   cd apps/web && npx playwright test -c journeys/playwright.config.ts
 * One worker, in file order: steps change seeded records that other steps of the same journey read.
 */
export default defineConfig({
  testDir: ".",
  testMatch: /J-[A-Z]+\.spec\.ts$/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  outputDir: "../test-results/journeys/artifacts",
  reporter: [
    ["list"],
    ["html", { outputFolder: "../playwright-report/journeys", open: "never" }],
    ["json", { outputFile: "../test-results/journeys/results.json" }],
    ["./board-reporter.ts"],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "retain-on-failure",
    timezoneId: "Asia/Kolkata",
    locale: "en-IN",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
