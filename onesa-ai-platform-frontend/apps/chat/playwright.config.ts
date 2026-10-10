import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  projects: ["chromium", "firefox", "webkit"].map(browserName => ({name: browserName, use: {browserName: browserName as "chromium" | "firefox" | "webkit"}})),
  use: {
    baseURL: process.env.ONESA_BROWSER_URL || "http://localhost:3100",

    // Local acceptance CA is verified independently; this opt-in affects this browser context only.
    ignoreHTTPSErrors: process.env.ONESA_LOCAL_TLS_TEST === "1",
  },
  reporter: "list",
});
