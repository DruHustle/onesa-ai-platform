import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { randomUUID } from "node:crypto";
const ownedUsers = new WeakMap<Page, string>();
const password = "industrial-synthetic-only-password-123!";
async function headers(context: BrowserContext, origin: string) {
  return {
    Origin: origin,
    "X-CSRF-Token":
      (await context.cookies(origin)).find((c) => c.name === "onesa_csrf")
        ?.value || "",
  };
}
async function register(page: Page, baseURL: string) {
  const origin = new URL(baseURL);
  if (!["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname))
    throw Error(
      "Industrial synthetic fixtures are loopback-only; hosted execution forbidden",
    );
  const ready = await page.request.get("/ready");
  expect(ready.status()).toBe(200);
  expect((await ready.json()).backend).toBe("mock");
  const email = `industrial-${randomUUID()}@example.com`;
  const result = await page.request.post("/api/v1/auth/register", {
    headers: { Origin: origin.origin },
    data: { email, password, display_name: "Synthetic industrial reviewer" },
  });
  expect(result.status()).toBe(201);
  ownedUsers.set(page, email);
  return email;
}
async function cleanup(
  page: Page,
  context: BrowserContext,
  baseURL: string,
  email: string,
) {
  const login = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: new URL(baseURL).origin },
    timeout: 10000,
    data: { email, password },
  });
  expect(login.status()).toBe(200);
  const result = await page.request.post("/api/v1/account/delete", {
    headers: await headers(context, new URL(baseURL).origin),
    timeout: 10000,
    data: { current_password: password, confirmation: "DELETE MY ACCOUNT" },
  });
  expect(result.status()).toBe(204);
}
async function create(page: Page) {
  await page.goto("/industrial");
  await page
    .getByRole("button", { name: "Review source coverage", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create investigation", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Calculated facts" }),
  ).toContainText("12");
  await expect(
    page.getByRole("heading", { name: "2. Observed evidence", exact: true }),
  ).toBeVisible();
}
test("actual synthetic workflow: facts, mock explanation, failed save, dirty navigation, review and reopen", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(90000);
  await register(page, baseURL!);
  await create(page);
  await page
    .getByRole("button", { name: "Run investigation", exact: true })
    .click();
  await expect(
    page.getByText("MOCK · No real model response", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", {
      name: "demo-press-01-reference · v1 · pressure-review",
      exact: true,
    })
    .click();
  await page
    .getByRole("button", { name: "Create internal draft", exact: true })
    .click();
  await page
    .getByLabel("Draft text", { exact: true })
    .fill(
      "Synthetic draft: check evidence with an engineer. No equipment instruction.",
    );
  await page.route("**/api/v1/industrial/investigations/*/draft", (r) =>
    r.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "synthetic_outage", message: "Synthetic failure" },
      }),
    }),
  );
  await page
    .getByRole("button", { name: "Save internal draft", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "entries are kept" }),
  ).toBeVisible();
  await expect(page.getByLabel("Draft text", { exact: true })).toHaveValue(
    /Synthetic draft/,
  );
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("link", { name: "Travel", exact: true }).click();
  await expect(page).toHaveURL(/\/industrial(?:#.*)?$/);
  await page.unroute("**/api/v1/industrial/investigations/*/draft");
  await page
    .getByRole("button", { name: "Save internal draft", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Internal draft saved" }),
  ).toBeVisible();
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Synthetic software evaluation, no physical work approved.");
  await page
    .getByRole("button", { name: "Record accepted", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: /^Owner self-review recorded;/ }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: /demo-press-01.*completed/ }).click();
  await expect(page.getByLabel("Draft text", { exact: true })).toHaveValue(
    /Synthetic draft/,
  );
  await expect(page.getByText(/accepted · r/)).toBeVisible();
});

test("pending cancellation blocks selection and reports an already-finished result accurately", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(90000);
  await register(page, baseURL!);
  await create(page);
  const list = await (
    await page.request.get("/api/v1/industrial/investigations")
  ).json();
  const original = list.items[0];
  const completeResponse = await page.request.post(
    `/api/v1/industrial/investigations/${original.id}/generate`,
    {
      headers: await headers(page.context(), new URL(baseURL!).origin),
      data: { expected_revision: original.revision },
    },
  );
  expect(completeResponse.status()).toBe(200);
  const complete = await completeResponse.json();
  const secondResponse = await page.request.post(
    "/api/v1/industrial/investigations",
    {
      headers: await headers(page.context(), new URL(baseURL!).origin),
      data: {
        id: randomUUID(),
        asset_id: "demo-conveyor-02",
        scenario: "reference",
        start: "2026-10-20T09:00:00Z",
        end: "2026-10-20T10:00:00Z",
      },
    },
  );
  expect(secondResponse.status()).toBe(201);
  const second = await secondResponse.json();
  const running = {
    ...complete,
    status: "running",
    revision: complete.revision + 1,
    payload: { ...complete.payload, explanation: null },
  };
  await page.route("**/api/v1/industrial/investigations", (r) =>
    r.fulfill({ status: 200, json: { items: [running, second] } }),
  );
  await page.reload();
  await page.getByRole("button", { name: /demo-press-01.*running/ }).click();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route(
    `**/api/v1/industrial/investigations/${original.id}`,
    async (r) => {
      await gate;
      await r.fulfill({
        status: 200,
        json: { ...complete, revision: running.revision + 1 },
      });
    },
  );
  let cancelWrites = 0;
  await page.route("**/api/v1/industrial/investigations/*/cancel", (r) => {
    cancelWrites++;
    return r.abort();
  });
  const request = page.waitForRequest(
    (r) =>
      new URL(r.url()).pathname ===
        `/api/v1/industrial/investigations/${original.id}` &&
      r.method() === "GET",
  );
  await page
    .getByRole("button", { name: "Cancel generation", exact: true })
    .click();
  await request;
  try {
    await expect(
      page.getByRole("button", { name: /demo-conveyor-02/ }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "New investigation", exact: true }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Cancel generation", exact: true }),
    ).toBeDisabled();
  } finally {
    release();
  }
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Generation has already ended. Saved state loaded." }),
  ).toBeVisible();
  expect(cancelWrites).toBe(0);
});

test("refresh reconciles the visible saved draft and protects unsaved text and review notes", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(90000);
  await register(page, baseURL!);
  await create(page);
  await page
    .getByRole("button", { name: "Run investigation", exact: true })
    .click();
  await expect(
    page.getByText("MOCK · No real model response", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create internal draft", exact: true })
    .click();
  await page
    .getByLabel("Draft text", { exact: true })
    .fill("Original saved synthetic draft.");
  await page
    .getByRole("button", { name: "Save internal draft", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Internal draft saved" }),
  ).toBeVisible();
  const list = await (
    await page.request.get("/api/v1/industrial/investigations")
  ).json();
  const saved = list.items[0];
  const remoteText = "Newer saved synthetic draft from another editor.";
  const response = await page.request.put(
    `/api/v1/industrial/investigations/${saved.id}/draft`,
    {
      headers: await headers(page.context(), new URL(baseURL!).origin),
      data: { expected_revision: saved.revision, text: remoteText },
    },
  );
  expect(response.status()).toBe(200);
  const remote = await response.json();
  await page
    .getByRole("button", { name: "Refresh saved state", exact: true })
    .click();
  await expect(page.getByLabel("Draft text", { exact: true })).toHaveValue(
    remoteText,
  );
  await page
    .getByLabel("Draft text", { exact: true })
    .fill("Unsaved local text must survive Stay.");
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Unsaved review note.");
  let prompted = false;
  page.once("dialog", (dialog) => {
    prompted = true;
    return dialog.dismiss();
  });
  await page
    .getByRole("button", { name: "Refresh saved state", exact: true })
    .click();
  await expect.poll(() => prompted).toBe(true);
  await expect(page.getByLabel("Draft text", { exact: true })).toHaveValue(
    "Unsaved local text must survive Stay.",
  );
  await expect(page.getByLabel("Review note", { exact: true })).toHaveValue(
    "Unsaved review note.",
  );
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Refresh saved state", exact: true })
    .click();
  await expect(page.getByLabel("Draft text", { exact: true })).toHaveValue(
    remoteText,
  );
  await expect(page.getByLabel("Review note", { exact: true })).toHaveValue("");
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Synthetic review of the displayed saved revision.");
  await page
    .getByRole("button", { name: "Record accepted", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: /^Owner self-review recorded;/ }),
  ).toBeVisible();
  const reviewed = await (
    await page.request.get(`/api/v1/industrial/investigations/${saved.id}`)
  ).json();
  expect(reviewed.payload.draft).toBe(remoteText);
  expect(reviewed.payload.review.reviewed_revision).toBe(remote.revision);
});

for (const colorScheme of ["light", "dark"] as const) {
  test.describe(`system ${colorScheme}`, () => {
    test.use({ colorScheme, reducedMotion: "reduce" });
    test("rendered synthetic investigation: EN/DE, mobile, landscape, keyboard and enlarged text", async ({
      page,
      baseURL,
    }, info) => {
      test.setTimeout(120000);
      await register(page, baseURL!);
      await create(page);
      // A live media change must finish propagating inherited foreground styles
      // before sampling contrast. A mismatched foreground still fails this check.
      await expect
        .poll(() =>
          page.evaluate(() => ({
            scheme: getComputedStyle(document.documentElement).colorScheme,
            foreground: getComputedStyle(document.body).color,
          })),
        )
        .toEqual({
          scheme: colorScheme,
          foreground:
            colorScheme === "dark" ? "rgb(229, 237, 246)" : "rgb(16, 38, 62)",
        });
      for (const viewport of [
        { width: 320, height: 568 },
        { width: 390, height: 844 },
        { width: 430, height: 932 },
        { width: 844, height: 390 },
        { width: 1440, height: 1000 },
      ]) {
        await page.setViewportSize(viewport);
        for (const locale of ["en", "de"]) {
          await page
            .getByLabel(/Interface language|Sprache der Oberfläche/)
            .selectOption(locale);
          await expect(
            page.getByRole("heading", {
              name:
                locale === "de"
                  ? "2. Beobachtete Belege"
                  : "2. Observed evidence",
            }),
          ).toBeVisible();
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth,
            ),
          ).toBe(true);
          const appearance = await page.evaluate(() => ({
            scheme: getComputedStyle(document.documentElement).colorScheme,
            body: getComputedStyle(document.body).color,
            heading: getComputedStyle(document.querySelector("h1")!).color,
            brand: getComputedStyle(document.querySelector(".brand")!).color,
          }));
          const violations = (
            await new AxeBuilder({ page })
              .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
              .analyze()
          ).violations;
          if (violations.length) {
            await info.attach("appearance-at-accessibility-failure", {
              body: JSON.stringify({
                colorScheme,
                viewport,
                locale,
                appearance,
                violations,
              }),
              contentType: "application/json",
            });
            await page.screenshot({
              path: info.outputPath("appearance-failure.png"),
              fullPage: true,
            });
          }
          expect(
            violations.map((v) => ({
              id: v.id,
              targets: v.nodes.map((n) => n.target),
            })),
          ).toEqual([]);
          if (viewport.width === 390 && locale === "en")
            await page.screenshot({
              path: info.outputPath(`industrial-${colorScheme}-390.png`),
              fullPage: true,
            });
        }
      }
      await page
        .getByLabel(/Interface language|Sprache der Oberfläche/)
        .selectOption("en");
      await page.addStyleTag({ content: "html{font-size:125%}" });
      await page.setViewportSize({ width: 390, height: 844 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page
        .getByRole("button", { name: "Run investigation", exact: true })
        .focus();
      await expect(
        page.getByRole("button", { name: "Run investigation", exact: true }),
      ).toBeFocused();
    });
  });
}

test.afterEach(async ({ page, context, baseURL }, info) => {
  const email = ownedUsers.get(page);
  if (!email) return;
  try {
    await cleanup(page, context, baseURL!, email);
    ownedUsers.delete(page);
  } catch (error) {
    await info.attach("owned-synthetic-cleanup-outcome", {
      body: JSON.stringify({
        status: "NOT_CONFIRMED",
        category: error instanceof Error ? error.name : "Unknown",
        production: false,
      }),
      contentType: "application/json",
    });
    if (info.status === info.expectedStatus) throw error;
  }
});
