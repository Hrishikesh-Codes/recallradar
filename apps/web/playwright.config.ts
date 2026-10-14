import { defineConfig, devices } from "@playwright/test";

const PORT = 3100;

/** E2E against the production build (`pnpm build` first): desktop, Android and iPhone, reduced motion. */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
    // Safari's engine: iPhones get the ZXing barcode fallback, not the native BarcodeDetector.
    { name: "iphone", use: { ...devices["iPhone 15"] } },
    {
      name: "reduced-motion",
      use: { ...devices["Desktop Chrome"], contextOptions: { reducedMotion: "reduce" } },
    },
  ],
  webServer: {
    command: `pnpm start --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
