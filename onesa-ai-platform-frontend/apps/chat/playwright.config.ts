import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: process.env.ONESA_BROWSER_URL || "http://localhost:3100",
    browserName: "chromium",
    // Local acceptance CA is verified independently; this opt-in affects this browser context only.
    ignoreHTTPSErrors: process.env.ONESA_LOCAL_TLS_TEST === "1",
  },
  reporter: "list",
});
