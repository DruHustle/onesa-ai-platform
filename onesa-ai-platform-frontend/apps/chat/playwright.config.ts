import { defineConfig } from "@playwright/test";
const target = new URL(process.env.ONESA_BROWSER_URL || "http://localhost:3100");
// Only credential-free CI against loopback fixtures may retain network traces.
const isolatedCI = process.env.CI === "true" &&
  ["localhost", "127.0.0.1", "[::1]"].includes(target.hostname);
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  projects: ["chromium", "firefox", "webkit"].map(browserName => ({name: browserName, use: {browserName: browserName as "chromium" | "firefox" | "webkit"}})),
  use: {
    timezoneId: "Europe/Berlin",
    trace: isolatedCI ? "retain-on-failure" : "off",
    screenshot: isolatedCI ? "only-on-failure" : "off",
    baseURL: process.env.ONESA_BROWSER_URL || "http://localhost:3100",

    // Local acceptance CA is verified independently; this opt-in affects this browser context only.
    ignoreHTTPSErrors: process.env.ONESA_LOCAL_TLS_TEST === "1",
  },
  reporter: "list",
});
