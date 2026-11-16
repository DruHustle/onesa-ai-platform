import {test, expect, type Route} from "@playwright/test";
const reply = (route: Route, body: unknown, status = 200) => route.fulfill({status, contentType: "application/json", body: JSON.stringify(body)});
test.beforeEach(async ({page, baseURL}) => {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL!).hostname)) throw Error("Loopback UI fixtures only");
  await page.route("**/api/**", route => reply(route, {}, 404));
  await page.route("**/api/v1/auth/me", route => reply(route, {id: "synthetic-owner", display_name: "Synthetic owner"}));
  await page.route("**/api/v1/documentation/access", route => reply(route, {engineering: false}));
  await page.route("**/api/v1/models", route => reply(route, {items: []}));
  await page.route("**/api/v1/industrial/assets", route => reply(route, {}, 404));
});
test("Chat pages, older owned document detail, reload and Back preserve selection", async ({page}) => {
  const reads: string[] = [];
  await page.route("**/api/v1/conversations{,?*}", route => {
    const cursor = new URL(route.request().url()).searchParams.get("cursor"); reads.push(cursor || "first");
    return reply(route, {items: [{id: cursor ? "older" : "newer", title: cursor ? "Older conversation" : "Recent conversation"}], next_cursor: cursor ? null : "synthetic-next"});
  });
  await page.route("**/api/v1/conversations/*", route => reply(route, {messages: [{id: "message", role: "assistant", content: {text: route.request().url().includes("older") ? "Older saved response" : "Recent saved response"}}]}));
  await page.route("**/api/v1/knowledge/documents{,?*}", route => reply(route, {items: [{id: "recent-document", title: "Recent notes"}], next_cursor: null}));
  await page.route("**/api/v1/knowledge/documents/older-document", route => reply(route, {id: "older-document", title: "Older owned source", text: "Permitted synthetic source"}));
  await page.goto("/?document=older-document");
  await expect(page.getByLabel("Message Onesa AI")).toBeEnabled();
  await page.getByRole("button", {name: "Recent conversation", exact: true}).click();
  await expect(page.getByText("Recent saved response", {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Older records", exact: true}).click();
  await page.getByRole("button", {name: "Older conversation", exact: true}).click();
  await expect(page.getByText("Older saved response", {exact: true})).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", {name: "Older conversation", exact: true})).toBeVisible();
  await expect(page.getByText("Older saved response", {exact: true})).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("button", {name: "Recent conversation", exact: true})).toBeVisible();
  await expect(page.getByText("Recent saved response", {exact: true})).toBeVisible();
  await page.getByText("Use documents (1 selected)", {exact: true}).click();
  await expect(page.getByLabel("Older owned source", {exact: true})).toBeChecked();
  expect(reads).toContain("synthetic-next");
});
for (const kind of ["agents", "travel"] as const) test(`${kind}: older page, failed read and retry retain an unsent draft with no mutation replay`, async ({page}) => {
  const path = kind === "agents" ? "agents/runs" : "travel/trips";
  let failed = false, writes = 0;
  const row = (older: boolean) => kind === "agents" ? {id: older ? "old" : "new", goal: older ? "Older tool run" : "Recent tool run", status: "completed", steps: [], created_at: "2026-10-24T00:00:00Z"}
    : {id: older ? "old" : "new", destination: older ? "Older trip" : "Recent trip", duration: 2, budget: 100, currency: "EUR", preferences: "", revision: 1, itinerary: {days: [], assumptions: [], backend: "mock"}, notice: "Synthetic itinerary"};
  await page.route(`**/api/v1/${path}{,?*}`, route => {
    if (route.request().method() !== "GET") {writes++; return reply(route, {}, 503);}
    const older = new URL(route.request().url()).searchParams.has("cursor");
    if (older && !failed) {failed = true; return reply(route, {}, 503);}
    return reply(route, {items: [row(older)], next_cursor: older ? null : "older-page"});
  });
  await page.goto(`/${kind}`);
  const draft = page.getByLabel(kind === "agents" ? "Text to analyze" : "Destination", {exact: true});
  await draft.fill("Unsent synthetic draft");
  await page.getByRole("button", {name: "Older records", exact: true}).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("unavailable");
  await expect(draft).toHaveValue("Unsent synthetic draft");
  await page.getByRole("button", {name: "Retry history", exact: true}).click();
  await expect(page.getByRole(kind === "agents" ? "heading" : "button", {name: kind === "agents" ? "Older tool run" : "Older trip · 2 days", exact: true})).toBeVisible();
  await expect(draft).toHaveValue("Unsent synthetic draft");
  expect(writes).toBe(0);
});
test("a conversation response from a signed-out account cannot enter a later session", async ({page}) => {
  let owner = "first-owner";
  await page.route("**/api/v1/conversations{,?*}", route => reply(route, {
    items: owner === "first-owner" ? [{id: "held-detail", title: "First account conversation"}] : [], next_cursor: null,
  }));
  await page.route("**/api/v1/knowledge/documents{,?*}", route => reply(route, {items: [], next_cursor: null}));
  let release!: () => void, observed!: () => void;
  const pending = new Promise<void>(resolve => {release = resolve;});
  const requested = new Promise<void>(resolve => {observed = resolve;});
  await page.route("**/api/v1/conversations/held-detail", async route => {
    observed(); await pending;
    await reply(route, {messages: [{id: "private", role: "assistant", content: {text: "First account private response"}}]}).catch(() => {});
  });
  await page.route("**/api/v1/auth/logout", route => reply(route, {}));
  await page.route("**/api/v1/auth/login", route => {
    owner = "second-owner";
    return reply(route, {id: owner, display_name: "Second account"});
  });
  try {
    await page.goto("/");
    await page.getByRole("button", {name: "First account conversation", exact: true}).click();
    await requested;
    await page.getByRole("button", {name: "Sign out", exact: true}).click();
    await page.getByLabel("Email", {exact: true}).fill("second@example.com");
    await page.getByLabel("Password", {exact: true}).fill("synthetic-placeholder-password");
    await page.getByRole("button", {name: "Sign in", exact: true}).click();
    await expect(page.getByLabel("Message Onesa AI")).toBeEnabled();
    const response = page.waitForResponse("**/api/v1/conversations/held-detail");
    release(); await response;
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await expect(page.getByText("First account private response", {exact: true})).toHaveCount(0);
    await expect(page.getByRole("button", {name: "First account conversation", exact: true})).toHaveCount(0);
    await expect(page).not.toHaveURL(/conversation=held-detail/);
  } finally {release();}
});
