import { test, expect, type Route } from "@playwright/test";

const method = { enabled: true, account_url: "https://account.example.test/account" };
const user = { id: "shared-user", email: "shared@example.com", display_name: "Shared user", identity_mode: "onesa", global_admin: false, administrator: false };
async function json(route: Route, value: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
}

test.beforeEach(async ({ context, baseURL }) => {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL || "http://localhost:3100").hostname))
    throw new Error("Shared identity fixtures require a loopback-only frontend");
  await context.route("**/api/**", route => json(route, { error: { code: "fixture_missing", message: "No fixture" } }, 404));
  await context.route("**/api/v1/auth/onesa/config", route => json(route, method));
  await context.route("**/api/v1/auth/me", route => json(route, { error: { code: "unauthorized", message: "Sign in" } }, 401));
  await context.route("https://account.example.test/**", route => route.fulfill({ contentType: "text/html", body: "<h1>Synthetic central account</h1>" }));
});

for (const locale of ["en", "de"] as const) {
  test(`${locale}: one account entry is clear, keyboard reachable and fits mobile`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "onesa_ui_locale", value: locale, url: baseURL || "http://localhost:3100" }]);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const button = page.getByRole("button", { name: locale === "de" ? "Mit Onesa fortfahren" : "Continue with Onesa", exact: true });
    await expect(button).toBeVisible();
    await expect(page.locator('input[type="password"]')).toHaveCount(0);
    await expect(page.getByRole("link", { name: locale === "de" ? "Onesa-Konto erstellen" : "Create an Onesa account" })).toHaveAttribute("href", method.account_url + "/register");
    await button.focus();
    await expect(button).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("the shared sign-in button starts only the central code flow", async ({ page }) => {
  let starts = 0;
  await page.route("**/api/v1/auth/onesa/start", route => {
    starts += 1;
    expect(route.request().postDataJSON()).toEqual({ next: "/?next=%2Fknowledge", reauthenticate: false });
    return json(route, { authorize_url: "https://account.example.test/api/v1/identity/auth?state=synthetic" });
  });
  await page.goto("/?next=%2Fknowledge");
  await page.getByRole("button", { name: "Continue with Onesa", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Synthetic central account" })).toBeVisible();
  expect(starts).toBe(1);
});

test("a sign-in failure gives a retry without showing a second password form", async ({ page }) => {
  await page.route("**/api/v1/auth/onesa/start", route => json(route, { error: { code: "identity_unavailable", message: "Onesa sign-in is temporarily unavailable" } }, 503));
  await page.goto("/");
  const button = page.getByRole("button", { name: "Continue with Onesa", exact: true });
  await button.click();
  await expect(page.getByRole("alert").filter({ hasText: "Onesa sign-in is temporarily unavailable" })).toBeVisible();
  await expect(button).toBeEnabled();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
});

test("existing data is connected only after explicit local account proof", async ({ page }) => {
  let proofs = 0;
  await page.route("**/api/v1/auth/onesa/link", route => {
    proofs += 1;
    expect(route.request().postDataJSON().email).toBe("shared@example.com");
    return json(route, { error: { code: "identity_link_invalid", message: "The existing application credentials could not be verified" } }, 403);
  });
  await page.goto("/?identity=link_required");
  await expect(page.getByRole("heading", { name: "Connect your existing AI account" })).toBeVisible();
  expect(proofs).toBe(0);
  await page.getByLabel("Email", { exact: true }).fill("shared@example.com");
  await page.getByLabel("Existing AI password", { exact: true }).fill("synthetic-old-password");
  await page.getByRole("button", { name: "Connect account", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "could not be verified" })).toBeVisible();
  await expect(page.getByLabel("Existing AI password", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Email", { exact: true })).toHaveValue("shared@example.com");
  expect(proofs).toBe(1);
});

test("shared account settings offer one administration hub and explicit step-up", async ({ page }) => {
  await page.route("**/api/v1/auth/me", route => json(route, { ...user, global_admin: true, administrator: true }));
  await page.route("**/api/v1/auth/sessions", route => json(route, { items: [], total: 0, limit: 100 }));
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Your Onesa account" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Manage access across applications" })).toHaveAttribute("href", method.account_url + "?tab=access");
  await expect(page.getByRole("link", { name: "Confirm Onesa sign-in in a new window" })).toHaveAttribute("target", "_blank");
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Delete AI workspace data" })).toBeVisible();
});

test("reauthentication preserves an existing chat draft in its original window", async ({ page, context }) => {
  let active = true;
  await context.route("**/api/v1/auth/me", route => active ? json(route, user) : json(route, { error: { code: "unauthorized", message: "Sign in" } }, 401));
  await context.route("**/api/v1/models", route => json(route, { items: [] }));
  for (const path of ["conversations", "knowledge/documents"])
    await context.route(`**/api/v1/${path}{,?*}`, route => json(route, { items: [], total: 0, limit: 20, offset: 0 }));
  await context.route("**/api/v1/documentation/access", route => json(route, { engineering: false }));
  await context.route("**/api/v1/auth/onesa/start", route => json(route, { authorize_url: "https://account.example.test/api/v1/identity/auth" }));
  await page.goto("/");
  await page.getByLabel("Message Onesa AI").fill("Keep this unfinished thought");
  active = false;
  await page.evaluate(() => window.dispatchEvent(new Event("onesa-session-expired")));
  const popup = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Continue with Onesa", exact: true }).click();
  const signIn = await popup;
  active = true;
  await expect(page.getByLabel("Message Onesa AI")).toHaveValue("Keep this unfinished thought", { timeout: 10000 });
  await signIn.close();
});


test("configuration failure offers a retry before any credential form", async ({ page }) => {
  await page.route("**/api/v1/auth/onesa/config", route => json(route, { error: { code: "unavailable", message: "Unavailable" } }, 503));
  await page.goto("/");
  await expect(page.getByRole("alert").filter({ hasText: "could not load the sign-in method" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry sign-in", exact: true })).toBeEnabled();
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
});

test("completion page verifies the session before confirming sign-in", async ({ page }) => {
  await page.goto("/auth/complete");
  await expect(page.getByRole("alert").filter({ hasText: "could not confirm your sign-in" })).toBeVisible();
  await expect(page.getByText("Your Onesa sign-in is confirmed.", { exact: false })).toHaveCount(0);
});

test("partial global logout clears the local private workspace and shows the limitation", async ({ page }) => {
  await page.route("**/api/v1/auth/me", route => json(route, user));
  await page.route("**/api/v1/models", route => json(route, { items: [] }));
  for (const path of ["conversations", "knowledge/documents"])
    await page.route(`**/api/v1/${path}{,?*}`, route => json(route, { items: [], total: 0, limit: 20, offset: 0 }));
  await page.route("**/api/v1/documentation/access", route => json(route, { engineering: false }));
  await page.route("**/api/v1/auth/logout", route => json(route, { error: { code: "identity_logout_incomplete", message: "Signed out here. Central sign-out is unavailable" } }, 503));
  await page.goto("/");
  await page.getByLabel("Message Onesa AI").fill("Private draft to clear");
  await page.getByRole("button", { name: "Sign out of Onesa", exact: true }).click();
  await expect(page.getByRole("button", { name: "Continue with Onesa", exact: true })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Signed out here" })).toBeVisible();
  await expect(page.getByLabel("Message Onesa AI")).toHaveCount(0);
});
