import { defineConfig, devices } from "@playwright/test";

const useLiveBackend = process.env.PLAYWRIGHT_USE_LIVE_BACKEND === "1";
const skipWebServer =
  process.env.PLAYWRIGHT_SKIP_WEB_SERVER === "1" || useLiveBackend;
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_SERVER === "1";

const frontendBaseURL =
  process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4173";
const apiBaseURL =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  (useLiveBackend ? "http://127.0.0.1:5002" : "http://127.0.0.1:8787");

const webServer = skipWebServer
  ? undefined
  : [
      {
        command: "node ./support/mock-api-server.mjs",
        cwd: "/workspaces/traffic-app/tests",
        url: `${apiBaseURL}/health`,
        reuseExistingServer,
        timeout: 30_000,
      },
      {
        command: "npm run dev -- --host 127.0.0.1 --port 4173",
        cwd: "/workspaces/traffic-app/traffic-app",
        env: {
          ...process.env,
          VITE_PROD_URL: apiBaseURL,
        },
        url: frontendBaseURL,
        reuseExistingServer,
        timeout: 60_000,
      },
    ];

export default defineConfig({
  testDir: "./specs",
  timeout: 45_000,
  expect: {
    timeout: 8_000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  outputDir: "./test-results",
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "./playwright-report" }],
    ["./reporters/defect-reporter.mjs"],
  ],
  use: {
    baseURL: frontendBaseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    testIdAttribute: "data-testid",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
  webServer,
  metadata: {
    frontendBaseURL,
    apiBaseURL,
    useLiveBackend,
  },
});
