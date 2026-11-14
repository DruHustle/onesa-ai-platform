import {
  test,
  expect,
  type BrowserContext,
  type APIRequestContext,
} from "@playwright/test";
import { randomUUID } from "node:crypto";
const password = "third-review-synthetic-only-password-123!";
async function headers(context: BrowserContext, baseURL: string) {
  const token = (await context.cookies(baseURL)).find(
    (cookie) => cookie.name === "onesa_csrf",
  )?.value;
  return { Origin: new URL(baseURL).origin, "X-CSRF-Token": token || "" };
}
async function removeOwned(
  request: APIRequestContext,
  context: BrowserContext,
  baseURL: string,
  email: string,
) {
  const login = await request.post("/api/v1/auth/login", {
    headers: { Origin: new URL(baseURL).origin },
    data: { email, password },
  });
  expect(login.status()).toBe(200);
  const removed = await request.post("/api/v1/account/delete", {
    headers: await headers(context, baseURL),
    data: { current_password: password, confirmation: "DELETE MY ACCOUNT" },
  });
  expect(removed.status()).toBe(204);
}
test("actual isolated accounts: registration returns to Travel, drafts survive expiry, ownership stays enforced", async ({
  page,
  context,
  browser,
  baseURL,
}, info) => {
  test.setTimeout(90000);
  const origin = new URL(baseURL!);
  if (!["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname))
    throw new Error(
      "Authenticated synthetic fixtures require loopback; hosted targets are forbidden",
    );
  const ready = await page.request.get("/ready");
  expect(ready.status()).toBe(200);
  expect((await ready.json()).backend).toBe("mock");
  const email = `third-travel-${randomUUID()}@example.com`,
    otherEmail = `third-travel-${randomUUID()}@example.com`;
  let other: BrowserContext | null = null,
    otherCreated = false,
    ownerCreated = false;
  let failure: unknown;
  const errors: unknown[] = [];
  try {
    await page.goto("/travel");
    await expect(
      page.getByRole("button", { name: "Sign in and continue" }),
    ).toBeVisible();
    await expect(page.getByLabel("Destination", { exact: true })).toHaveCount(
      0,
    );
    await page
      .getByRole("link", { name: "Create an account", exact: true })
      .click();
    await expect
      .poll(() => new URL(page.url()).searchParams.get("next"))
      .toBe("/travel");
    await page
      .getByRole("button", { name: "New to Onesa? Create an account" })
      .click();
    await page.getByLabel("Display name").fill("Synthetic Travel reviewer");
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    const registrationResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/v1/auth/register") &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Create account", exact: true })
      .click();
    expect((await registrationResponse).status()).toBe(201);
    ownerCreated = true;
    await expect(page).toHaveURL(/\/travel$/);
    await expect(page.getByLabel("Destination", { exact: true })).toBeVisible();
    for (const destination of ["Lisbon", "Berlin"]) {
      if (destination === "Berlin")
        await page.getByRole("button", { name: "New trip" }).click();
      await page.getByLabel("Destination", { exact: true }).fill(destination);
      await page
        .getByRole("textbox", {
          name: "Interests and preferences",
          exact: true,
        })
        .fill("Synthetic museums and walking plan");
      await page
        .getByRole("button", { name: "Create plan", exact: true })
        .click();
      await expect(
        page.getByRole("heading", {
          name: destination + " · revision 1",
          exact: true,
        }),
      ).toBeVisible();
    }
    const items = (
      await (await page.request.get("/api/v1/travel/trips")).json()
    ).items;
    const a = items.find(
      (trip: { destination: string }) => trip.destination === "Lisbon",
    );
    expect(a).toBeTruthy();
    await page
      .getByRole("button", { name: "Lisbon · 3 days", exact: true })
      .click();
    const preferences = page.getByRole("textbox", {
      name: "Interests and preferences",
      exact: true,
    });
    await preferences.fill("Keep this private unsaved revision");
    page.once("dialog", (dialog) => dialog.dismiss());
    await page
      .getByRole("button", { name: "Berlin · 3 days", exact: true })
      .click();
    await expect(preferences).toHaveValue("Keep this private unsaved revision");
    let puts = 0;
    page.on("request", (request) => {
      if (
        request.method() === "PUT" &&
        request.url().endsWith("/travel/trips/" + a.id)
      )
        puts++;
    });
    expect(
      (
        await page.request.post("/api/v1/auth/logout", {
          headers: await headers(context, baseURL!),
        })
      ).status(),
    ).toBe(204);
    await page
      .getByRole("button", { name: "Revise plan", exact: true })
      .click();
    await expect(
      page.getByText("Your session expired or could not be verified.", {
        exact: false,
      }),
    ).toBeVisible();
    await expect(preferences).toBeHidden();
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in and continue" }).click();
    await expect(preferences).toHaveValue("Keep this private unsaved revision");
    await expect(
      page.getByRole("heading", {
        name: "Plan your next journey",
        exact: true,
      }),
    ).toBeFocused();
    expect(puts).toBe(1);
    const before = await page.request.get("/api/v1/travel/trips/" + a.id);
    expect(before.status()).toBe(200);
    expect((await before.json()).revision).toBe(1);
    await page
      .getByRole("button", { name: "Revise plan", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Lisbon · revision 2", exact: true }),
    ).toBeVisible();
    expect(puts).toBe(2);
    other = await browser.newContext({ baseURL });
    expect(
      (await other.request.get("/api/v1/travel/trips/" + a.id)).status(),
    ).toBe(401);
    const registration = await other.request.post("/api/v1/auth/register", {
      headers: { Origin: origin.origin },
      data: {
        email: otherEmail,
        password,
        display_name: "Synthetic isolated other user",
      },
    });
    expect(registration.status()).toBe(201);
    otherCreated = true;
    expect(
      (await other.request.get("/api/v1/travel/trips/" + a.id)).status(),
    ).toBe(404);
    const denied = await other.request.put("/api/v1/travel/trips/" + a.id, {
      headers: await headers(other, baseURL!),
      data: {
        destination: "Forbidden cross-user change",
        duration: 3,
        budget: 500,
        currency: "USD",
        preferences: "Synthetic negative test",
        expected_revision: 2,
      },
    });
    expect(denied.status()).toBe(404);
    const unchanged = await page.request.get("/api/v1/travel/trips/" + a.id);
    expect((await unchanged.json()).preferences).toBe(
      "Keep this private unsaved revision",
    );
    await page.screenshot({
      path: info.outputPath("authenticated-travel-preserved.png"),
      fullPage: true,
    });
  } catch (error) {
    failure = error;
  } finally {
    try {
      if (other && otherCreated)
        await removeOwned(other.request, other, baseURL!, otherEmail);
    } catch (error) {
      errors.push(error);
    }
    try {
      await other?.close();
    } catch (error) {
      errors.push(error);
    }
    try {
      if (ownerCreated)
        await removeOwned(page.request, context, baseURL!, email);
    } catch (error) {
      errors.push(error);
    }
  }
  if (failure) {
    await info.attach("owned-cleanup-result", {
      body: JSON.stringify({ errors: errors.map(String) }),
      contentType: "application/json",
    });
    throw failure;
  }
  if (errors.length)
    throw new AggregateError(errors, errors.map(String).join("\n"));
});
