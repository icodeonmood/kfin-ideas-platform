import { defineConfig, devices } from "@playwright/test";

// Runs against the local stack (`make up`); the web container listens on :3000 unless `.env` moves it (BLD-200).
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  // BLD-A244: CI also writes JUnit XML for the go/no-go report when `make e2e` passes E2E_JUNIT_FILE.
  reporter: process.env.E2E_JUNIT_FILE
    ? [["list"], ["junit", { outputFile: process.env.E2E_JUNIT_FILE }]]
    : [["list"]],
  use: { baseURL: process.env.E2E_BASE_URL || "http://localhost:3000", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "phone-360", use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 740 } } },
    // BLD-D038 proof only (throwaway branch, as lane A's 31e051d9): the same two widths with reduced motion, so no glide runs
    { name: "desktop-still", use: { ...devices["Desktop Chrome"], reducedMotion: "reduce" } },
    {
      name: "phone-360-still",
      use: { ...devices["Desktop Chrome"], viewport: { width: 360, height: 740 }, reducedMotion: "reduce" },
    },
  ],
});
