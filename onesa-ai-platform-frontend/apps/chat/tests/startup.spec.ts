import { test, expect, type Page, type Route } from "@playwright/test";

const anonymous = {
  status: 401,
  body: { error: { code: "unauthenticated", message: "Synthetic signed-out session" } },
};
const user = { id: "synthetic-startup-user", display_name: "Synthetic startup user", email: "startup@example.test" };

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function authenticated(page: Page) {
  await page.route("**/api/v1/auth/me", route => json(route, user));
  await page.route("**/api/v1/models", route => json(route, { items: [] }));
  await page.route("**/api/v1/conversations", route => json(route, { items: [] }));
  await page.route("**/api/v1/knowledge/documents", route => json(route, { items: [] }));
  await page.route("**/api/v1/documentation/access", route => json(route, { engineering: false }));
}

async function hold(page: Page, path: string, body: unknown, status = 200) {
  let release!: () => void;
  let observed!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const requested = new Promise<void>(resolve => { observed = resolve; });
  await page.route(`**/api/v1${path}`, async route => {
    observed();
    await pending;
    // A correctly cancelled startup request can be gone before the fixture releases it.
    await json(route, body, status).catch(() => {});
  });
  return { release, requested };
}

test.beforeEach(async ({ page, baseURL }) => {
  const target = new URL(baseURL ?? "http://localhost:3100");
  if (!["localhost", "127.0.0.1", "[::1]"].includes(target.hostname)) {
    throw new Error("Startup fixtures require an isolated loopback frontend; hosted targets are forbidden.");
  }
  // Every API request is intercepted, including accidental new endpoints and mock mutations.
  await page.route("**/api/**", route => json(route, {
    error: { code: "fixture_missing", message: "No synthetic fixture for this endpoint" },
  }, 404));
});

for (const locale of ["en", "de"] as const) {
  test(`${locale}: sign-in drafts are editable while session verification guards every submission`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "onesa_ui_locale", value: locale, url: baseURL ?? "http://localhost:3100" }]);
    const welcome = locale === "de" ? "Willkommen zurück" : "Welcome back";
    const email = locale === "de" ? "E-Mail" : "Email";
    const password = locale === "de" ? "Passwort" : "Password";
    const signIn = locale === "de" ? "Anmelden" : "Sign in";
    const response = await context.request.get("/");
    expect(response.ok()).toBe(true);
    const serverMain = (await response.text()).match(/<main\b[\s\S]*?<\/main>/)?.[0];
    expect(serverMain).toContain(welcome);
    expect(serverMain).toContain('name="email"');
    expect(serverMain).toContain('name="password"');
    expect(serverMain).not.toMatch(/<input(?=[^>]*name="email")(?=[^>]*disabled)[^>]*>/);

    const session = await hold(page, "/auth/me", anonymous.body, anonymous.status);
    const mutations: string[] = [];
    page.on("request", request => {
      const path = new URL(request.url()).pathname;
      if (request.method() === "POST" && ["/api/v1/auth/login", "/api/v1/auth/register"].includes(path)) mutations.push(path);
    });
    try {
      await page.goto("/");
      await session.requested;
      await expect(page.getByRole("heading", { name: welcome, exact: true })).toBeVisible();
      await expect(page.getByLabel(email, { exact: true })).toBeEnabled();
      await expect(page.getByLabel(password, { exact: true })).toBeEnabled();
      await page.getByLabel(email, { exact: true }).fill("draft@example.test");
      await page.getByLabel(password, { exact: true }).fill("synthetic-bootstrap-draft");
      await expect(page.getByRole("button", { name: signIn, exact: true })).toBeDisabled();
      await page.getByLabel(password, { exact: true }).press("Enter");
      await page.locator(".auth-card form").evaluate(form => (form as HTMLFormElement).requestSubmit());
      expect(mutations).toEqual([]);
      session.release();
      await expect(page.getByLabel(email, { exact: true })).toBeEnabled();
      await expect(page.getByRole("button", { name: signIn, exact: true })).toBeEnabled();
      await expect(page.getByLabel(email, { exact: true })).toHaveValue("draft@example.test");
      await expect(page.getByLabel(password, { exact: true })).toHaveValue("synthetic-bootstrap-draft");
      await expect(page.getByLabel(password, { exact: true })).toBeFocused();
      expect(mutations).toEqual([]);
      await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
    } finally {
      session.release();
    }
  });
}

test("a late verified session replaces the sign-in draft without replaying a login", async ({ page }) => {
  await authenticated(page);
  const session = await hold(page, "/auth/me", user);
  const mutations: string[] = [];
  page.on("request", request => {
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST" && ["/api/v1/auth/login", "/api/v1/auth/register"].includes(path)) mutations.push(path);
  });
  try {
    await page.goto("/");
    await session.requested;
    await page.getByLabel("Email", { exact: true }).fill("draft@example.test");
    await page.getByLabel("Password", { exact: true }).fill("synthetic-bootstrap-draft");
    await page.getByLabel("Password", { exact: true }).press("Enter");
    await page.locator(".auth-card form").evaluate(form => (form as HTMLFormElement).requestSubmit());
    expect(mutations).toEqual([]);
    session.release();
    await expect(page.getByLabel("Message Onesa AI")).toBeEnabled();
    await expect(page.getByRole("heading", { name: "Welcome back", exact: true })).toHaveCount(0);
    expect(mutations).toEqual([]);
  } finally {
    session.release();
  }
});

test("a hung session check is cancelled within ten seconds and retry preserves entered fields without reloading", async ({ page }) => {
  test.setTimeout(25000);
  let attempt = 0;
  let release!: () => void;
  let observed!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const requested = new Promise<void>(resolve => { observed = resolve; });
  const cancelled: string[] = [];
  page.on("requestfailed", request => {
    if (new URL(request.url()).pathname === "/api/v1/auth/me") cancelled.push(request.failure()?.errorText ?? "cancelled");
  });
  await page.route("**/api/v1/auth/me", async route => {
    attempt += 1;
    if (attempt === 1) {
      observed();
      await pending;
      await json(route, anonymous.body, anonymous.status).catch(() => {});
    } else await json(route, anonymous.body, anonymous.status);
  });
  let navigations = 0;
  page.on("request", request => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) navigations += 1;
  });
  try {
    await page.goto("/");
    await requested;
    const started = Date.now();
    await expect(page.getByRole("heading", { name: "Welcome back", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeDisabled();
    await expect(page.locator("main").getByRole("alert")).toContainText("The service is unavailable", { timeout: 10000 });
    expect(Date.now() - started).toBeLessThan(10000);
    await expect.poll(() => cancelled.length).toBeGreaterThan(0);
    await page.getByLabel("Email", { exact: true }).fill("retry@example.test");
    await page.getByLabel("Password", { exact: true }).fill("synthetic-retry-password");
    await page.getByRole("button", { name: "Retry connection", exact: true }).click();
    await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeEnabled();
    await expect(page.locator("main").getByRole("alert")).toHaveCount(0);
    await expect(page.getByLabel("Email", { exact: true })).toHaveValue("retry@example.test");
    await expect(page.getByLabel("Password", { exact: true })).toHaveValue("synthetic-retry-password");
    expect(attempt).toBe(2);
    expect(navigations).toBe(1);
  } finally {
    release();
  }
});

test("ordinary chat accepts an unsent draft while optional document loading is pending", async ({ page }) => {
  await authenticated(page);
  const documents = await hold(page, "/knowledge/documents", { items: [] });
  try {
    await page.goto("/");
    await documents.requested;
    const composer = page.getByLabel("Message Onesa AI");
    await expect(composer).toBeEnabled();
    await composer.fill("An unsent synthetic startup draft");
    await expect(page.getByLabel("Send message")).toBeEnabled();
    documents.release();
    await expect(composer).toHaveValue("An unsent synthetic startup draft");
  } finally {
    documents.release();
  }
});

test("a requested document remains blocked until its accessible document list is verified", async ({ page }) => {
  await authenticated(page);
  const documents = await hold(page, "/knowledge/documents", { items: [{ id: "synthetic-document", title: "Synthetic verified notes" }] });
  try {
    await page.goto("/?document=synthetic-document");
    await documents.requested;
    await expect(page.getByLabel("Message Onesa AI")).toBeDisabled();
    await expect(page.getByLabel("Send message")).toBeDisabled();
    documents.release();
    await expect(page.getByLabel("Message Onesa AI")).toBeEnabled();
    await expect(page.getByText("Use documents (1 selected)", { exact: true })).toBeVisible();
    await page.getByText("Use documents (1 selected)", { exact: true }).click();
    await expect(page.getByLabel("Synthetic verified notes", { exact: true })).toBeChecked();
  } finally {
    documents.release();
  }
});

for (const failure of ["inaccessible", "failed"] as const) {
  test(`a ${failure} requested document keeps chat blocked and reports the cause`, async ({ page }) => {
    await authenticated(page);
    await page.route("**/api/v1/knowledge/documents", route => failure === "inaccessible"
      ? json(route, { items: [{ id: "another-document", title: "Another synthetic document" }] })
      : json(route, { error: { code: "unavailable", message: "Synthetic document outage" } }, 503));
    await page.goto("/?document=synthetic-document");
    await expect(page.locator("main").getByRole("alert")).toContainText(failure === "inaccessible"
      ? "The selected document is unavailable" : "Unable to load the selected document");
    await expect(page.getByLabel("Message Onesa AI")).toBeDisabled();
    await expect(page.getByLabel("Send message")).toBeDisabled();
  });
}

test("saved messages load deferred Markdown with GFM tables and highlighted code", async ({ page }) => {
  await authenticated(page);
  const markdown = "| Item | Count |\n| --- | --- |\n| Synthetic row | 42 |\n\n```javascript\nconst fixture = 42;\n```";
  await page.route("**/api/v1/conversations", route => json(route, { items: [{ id: "synthetic-saved-chat", title: "Synthetic saved conversation" }] }));
  await page.route("**/api/v1/conversations/synthetic-saved-chat", route => json(route, {
    messages: [{ id: "synthetic-saved-message", role: "assistant", content: { text: markdown } }],
  }));
  const scripts = new Set<string>();
  page.on("request", request => {
    if (request.resourceType() === "script") scripts.add(new URL(request.url()).pathname);
  });
  await page.goto("/");
  await expect(page.getByLabel("Message Onesa AI")).toBeEnabled();
  await expect(page.getByRole("button", { name: "Synthetic saved conversation", exact: true })).toBeVisible();
  await page.waitForLoadState("networkidle");
  const initialScripts = new Set(scripts);
  await page.getByRole("button", { name: "Synthetic saved conversation", exact: true }).click();
  const message = page.locator(".message.assistant");
  await expect(message.getByRole("table")).toBeVisible();
  await expect(message.getByRole("cell", { name: "Synthetic row", exact: true })).toBeVisible();
  await expect(message.locator("code.language-javascript .hljs-keyword")).toHaveText("const");
  expect([...scripts].filter(path => !initialScripts.has(path)).length).toBeGreaterThan(0);
});

test("late optional startup responses cannot repopulate the next signed-in account", async ({ page }) => {
  await authenticated(page);
  const paths = ["/models", "/knowledge/documents", "/conversations"];
  const oldBodies = [
    { items: [{ backend: "mock", model_identifier: "old-model-fixture", real_inference: false }] },
    { items: [{ id: "old-document", title: "Old synthetic document" }] },
    { items: [{ id: "old-conversation", title: "Old synthetic conversation" }] },
  ];
  const freshBodies = [
    { items: [{ backend: "mock", model_identifier: "fresh-model-fixture", real_inference: false }] },
    { items: [{ id: "fresh-document", title: "Fresh synthetic document" }] },
    { items: [{ id: "fresh-conversation", title: "Fresh synthetic conversation" }] },
  ];
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  const requested = paths.map(() => {
    let observed!: () => void;
    const promise = new Promise<void>(resolve => { observed = resolve; });
    return { promise, observed };
  });
  for (const [index, path] of paths.entries()) {
    let attempts = 0;
    await page.route(`**/api/v1${path}`, async route => {
      attempts += 1;
      if (attempts === 1) {
        requested[index].observed();
        await pending;
        await json(route, oldBodies[index]).catch(() => {});
      } else await json(route, freshBodies[index]);
    });
  }
  await page.route("**/api/v1/auth/logout", route => json(route, {}));
  await page.route("**/api/v1/auth/login", route => json(route, { ...user, id: "fresh-synthetic-user", display_name: "Fresh synthetic user" }));
  try {
    await page.goto("/");
    await Promise.all(requested.map(item => item.promise));
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.getByLabel("Email", { exact: true }).fill("fresh@example.test");
    await page.getByLabel("Password", { exact: true }).fill("synthetic-fresh-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("button", { name: "Fresh synthetic conversation", exact: true })).toBeVisible();
    await expect(page.getByText("fresh-model-fixture", { exact: false })).toBeVisible();
    release();
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Fresh synthetic user", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Old synthetic conversation", exact: true })).toHaveCount(0);
    await expect(page.getByText("Old synthetic document", { exact: true })).toHaveCount(0);
    await expect(page.getByText("old-model-fixture", { exact: false })).toHaveCount(0);
    await page.getByText("Use documents (0 selected)", { exact: true }).click();
    await expect(page.getByLabel("Fresh synthetic document", { exact: true })).toBeVisible();
  } finally {
    release();
  }
});
