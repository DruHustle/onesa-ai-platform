import { test, expect, type Route } from "@playwright/test";

const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
test.beforeEach(async ({ page, baseURL }) => {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL!).hostname)) throw Error("Loopback fixtures only");
  await page.route("**/api/**", route => json(route, { error: { code: "fixture_missing", message: "Synthetic fixture" } }, 404));
  await page.route("**/api/v1/auth/me", route => json(route, { id: "synthetic", email: "review@example.test", display_name: "Synthetic" }));
  await page.route("**/api/v1/documentation/access", route => json(route, { engineering: false }));
  await page.route("**/api/v1/industrial/assets", route => json(route, { items: [{ id: "demo-press-01", name: "Demonstration press" }] }));
});
for (const [code, status, message] of [
  ["industrial_demo_disabled", 404, "not enabled on this environment"],
  ["not_found", 404, "not found or is not available to this account"],
  ["unavailable", 503, "Saved investigations could not be loaded"],
] as const) {
  test(`list error ${code} never claims an empty list`, async ({ page }) => {
    await page.route("**/api/v1/industrial/investigations", route => json(route, { error: { code, message: "Synthetic error" } }, status));
    await page.goto("/industrial");
    await expect(page.getByRole("alert").filter({ hasText: message })).toBeVisible();
    await expect(page.getByText("No saved investigations.", { exact: true })).toHaveCount(0);
  });
}
test("loading is distinct from confirmed empty", async ({ page }) => {
  let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/industrial/investigations", async route => { await waiting; await json(route, { items: [] }); });
  try {
    await page.goto("/industrial");
    await expect(page.getByRole("status").filter({ hasText: "Loading saved investigations" })).toBeVisible();
    await expect(page.getByText("No saved investigations.", { exact: true })).toHaveCount(0);
    release();
    await expect(page.getByText("No saved investigations.", { exact: true })).toBeVisible();
  } finally { release(); }
});
test("populated list remains visible", async ({ page }) => {
  await page.route("**/api/v1/industrial/investigations", route => json(route, { items: [{ id: "synthetic-row", status: "ready", revision: 1, payload: { selection: { asset_id: "demo-press-01" } } }] }));
  await page.goto("/industrial");
  await expect(page.getByRole("button", { name: /demo-press-01.*ready/ })).toBeVisible();
  await expect(page.getByText("No saved investigations.", { exact: true })).toHaveCount(0);
});

for (const status of [401, 403, 404, 503]) {
  test(`Industrial navigation stays absent when this API/account returns ${status}`, async ({ page }) => {
    await page.route("**/api/v1/industrial/assets", route => json(route, { error: { code: "synthetic_denial" } }, status));
    await page.route("**/api/v1/industrial/investigations", route => json(route, { items: [] }));
    const observed = page.waitForResponse(response => response.url().endsWith("/api/v1/industrial/assets"));
    await page.goto("/industrial");
    await observed;
    await expect(page.getByRole("heading", { name: "Industrial Investigation", exact: true })).toBeVisible();
    await expect(page.locator('nav[aria-label="AI workspace"] a[href="/industrial"]')).toHaveCount(0);
  });
}

test("Industrial navigation requires a valid eligible response and marks German content", async ({ page }) => {
  await page.route("**/api/v1/industrial/investigations", route => json(route, { items: [] }));
  await page.goto("/industrial");
  await expect(page.locator('nav[aria-label="AI workspace"] a[href="/industrial"]')).toHaveAttribute("aria-current", "page");
  await page.getByLabel("Interface language").selectOption("de");
  const content = page.locator("main.feature-shell > section");
  await expect(content).toHaveAttribute("lang", "de");
  await expect(content.getByRole("heading", {name: "1. Belege auswählen", exact: true})).toBeVisible();
  await page.getByLabel("Sprache der Oberfläche").selectOption("en");
  await expect(content).toHaveAttribute("lang", "en");
  await page.route("**/api/v1/industrial/assets", route => json(route, { unexpected: [] }));
  await page.reload();
  await expect(page.getByRole("heading", { name: "Industrial Investigation", exact: true })).toBeVisible();
  await expect(page.locator('nav[aria-label="AI workspace"] a[href="/industrial"]')).toHaveCount(0);
});

test("untranslated Travel content stays English after changing the interface language", async ({ page }) => {
  await page.goto("/travel");
  await page.getByLabel("Interface language").selectOption("de");
  await expect(page.locator("main.feature-shell > section").last()).toHaveAttribute("lang", "en");
});

test("German investigation keeps untranslated narrative and source passages marked English", async ({ page }) => {
  const payload = {
    selection: { asset_id: "demo-press-01", start: "2026-10-20T09:00:00Z", end: "2026-10-20T10:00:00Z" },
    snapshot_sha256: "a".repeat(64),
    facts: { event_count: 0, known_downtime_seconds: 0, distinct_downtime_episodes: 0, downtime_complete: true, incomplete_event_ids: [], timeline: [] },
    coverage: { missing: [], stale_signal_ids: [], reference_conflict: false, signal_coverage: "Synthetic fixture" },
    evidence: { fixture_version: "test-only", metadata_version: "1", signals: [], references: [{ id: "synthetic-source", version: "1", title: "Synthetic manual", anchor: "safety", text: "Review the source evidence.", rights: "Synthetic test fixture", sha256: "b".repeat(64) }] },
    explanation: { abstained: false, limitations: ["Synthetic limitations only."], hypotheses: [{ statement: "A synthetic hypothesis.", quote: "Review the source evidence.", human_review: "An engineer must review this.", citations: [{ document_id: "synthetic-source", version: "1", anchor: "safety" }] }] },
    generation: { mode: "mock", latency_ms: null, cost: null }, error: null, draft: null, review: null,
  };
  await page.route("**/api/v1/industrial/investigations", route => json(route, { items: [{ id: "synthetic-language", status: "ready", revision: 1, payload }] }));
  await page.goto("/industrial");
  await page.getByRole("button", { name: /demo-press-01.*ready/ }).click();
  await page.getByLabel("Interface language").selectOption("de");
  await expect(page.locator("main.feature-shell > section")).toHaveAttribute("lang", "de");
  for (const text of ["A synthetic hypothesis.", "An engineer must review this.", "Synthetic limitations only."])
    await expect(page.getByText(text, {exact: true})).toHaveAttribute("lang", "en");
  await expect(page.locator('details[id="source-synthetic-source-1-safety"]')).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", {name: "3. Hypothesen und Grenzen"})).toBeVisible();
});

test("catalog failure preserves a successfully loaded saved list", async ({ page }) => {
  await page.route("**/api/v1/industrial/assets", route => json(route, { error: { code: "unavailable", message: "Synthetic catalog outage" } }, 503));
  await page.route("**/api/v1/industrial/investigations", route => json(route, { items: [{ id: "synthetic-row", status: "ready", revision: 1, payload: { selection: { asset_id: "demo-press-01" } } }] }));
  await page.goto("/industrial");
  await expect(page.getByRole("button", { name: /demo-press-01.*ready/ })).toBeVisible();
  await expect(page.getByText("Saved investigations could not be loaded. Your entries are kept.", { exact: true })).toHaveCount(0);
});

test("a late initial empty list preserves a newly created investigation", async ({ page }) => {
  let release!: () => void;
  const waiting = new Promise<void>(resolve => { release = resolve; });
  const payload = {
    selection: { asset_id: "demo-press-01", start: "2026-10-20T09:00:00Z", end: "2026-10-20T10:00:00Z" },
    snapshot_sha256: "a".repeat(64),
    facts: { event_count: 3, known_downtime_seconds: 720, distinct_downtime_episodes: 3, downtime_complete: true, incomplete_event_ids: [], timeline: [] },
    coverage: { missing: [], stale_signal_ids: [], reference_conflict: false, signal_coverage: "Sparse synthetic samples" },
    evidence: { fixture_version: "onesa-industrial-synthetic-v1", metadata_version: "1", references: [], signals: [] },
    explanation: null, generation: null, error: null, draft: null, review: null,
  };
  await page.route("**/api/v1/industrial/evidence?**", route => json(route, payload));
  await page.route("**/api/v1/industrial/investigations", async route => {
    if (route.request().method() === "POST") {
      await json(route, { id: route.request().postDataJSON().id, status: "ready", revision: 1, created_at: "2026-10-20T10:00:00Z", updated_at: "2026-10-20T10:00:00Z", payload }, 201);
    } else { await waiting; await json(route, { items: [] }); }
  });
  try {
    await page.goto("/industrial");
    await expect(page.getByRole("status").filter({ hasText: "Loading saved investigations" })).toBeVisible();
    await page.getByRole("button", { name: "Review source coverage", exact: true }).click();
    await page.getByRole("button", { name: "Create investigation", exact: true }).click();
    await expect(page.getByRole("button", { name: /demo-press-01.*ready/ })).toBeVisible();
    release();
    await expect(page.getByRole("status").filter({ hasText: "Loading saved investigations" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /demo-press-01.*ready/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "2. Observed evidence", exact: true })).toBeVisible();
  } finally { release(); }
});
