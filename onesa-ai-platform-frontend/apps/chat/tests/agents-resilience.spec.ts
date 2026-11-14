import { test, expect, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const reply = (route: Route, body: unknown, status = 200) => route.fulfill({
  status, contentType: "application/json", body: JSON.stringify(body),
});
test.beforeEach(async ({ page, baseURL }) => {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL!).hostname)) {
    throw new Error("Synthetic fixtures require loopback; hosted targets are forbidden.");
  }
  await page.route("**/api/**", route => reply(route, {}, 503));
  await page.route("**/api/v1/auth/me", route => reply(route, { id: "synthetic-operator" }));
  await page.route("**/api/v1/documentation/access", route => reply(route, { engineering: false }));
});

for (const colorScheme of ["light", "dark"] as const) {
  test(`${colorScheme}: unavailable history preserves drafts and retries without replaying a run`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ colorScheme });
    let reads = 0;
    const writes: unknown[] = [];
    await page.route("**/api/v1/agents/runs{,?*}", route => {
      if (route.request().method() === "POST") { writes.push(route.request().postDataJSON()); return reply(route, {}, 503); }
      reads += 1;
      return reads === 1 ? reply(route, {}, 503) : reply(route, { items: [] });
    });
    await page.goto("/agents");
    await expect(page.locator("main").getByRole("alert")).toContainText("Run history is unavailable");
    await expect(page.getByText("Your results will appear here")).toHaveCount(0);
    await page.getByLabel("Text to analyze").fill("Keep this synthetic draft");
    await page.getByRole("button", { name: "Retry history" }).click();
    await expect(page.getByText("Your results will appear here")).toBeVisible();
    await expect(page.getByLabel("Text to analyze")).toHaveValue("Keep this synthetic draft");
    expect(writes).toEqual([]);
    expect(reads).toBe(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`agents-${colorScheme}.png`), fullPage: true });
  });
}

test("explicit text-statistics run requires permission and displays counts without another history request", async ({ page }) => {
  let reads = 0;
  const writes: unknown[] = [];
  await page.route("**/api/v1/agents/runs{,?*}", route => {
    if (route.request().method() !== "POST") { reads += 1; return reply(route, { items: [] }); }
    writes.push(route.request().postDataJSON());
    return reply(route, { id: "synthetic-run", goal: "Count these words", status: "completed", created_at: "2026-10-16T10:00:00Z",
      steps: [{ status: "completed", tool: "text_stats", result: { words: 3, characters: 17 } }] }, 201);
  });
  await page.goto("/agents");
  await expect(page.getByText("Your results will appear here")).toBeVisible();
  await page.getByLabel("Text to analyze").fill("Count these words");
  await expect(page.getByRole("button", { name: "Run tool", exact: true })).toBeDisabled();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Run tool", exact: true }).click();
  await expect(page.locator(".tool-results")).toContainText("Words3");
  await expect(page.locator(".tool-results")).toContainText("Characters17");
  expect(writes).toEqual([{ goal: "Count these words", allowed_tools: ["text_stats"], steps: [{ tool: "text_stats", arguments: { text: "Count these words" } }] }]);
  expect(reads).toBe(1);
});

test("uncertain submission keeps the draft and never automatically retries", async ({ page }) => {
  let writes = 0;
  await page.route("**/api/v1/agents/runs{,?*}", route => {
    if (route.request().method() === "POST") { writes += 1; return reply(route, {}, 503); }
    return reply(route, { items: [] });
  });
  await page.goto("/agents");
  await page.getByLabel("Text to analyze").fill("Preserve this text");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Run tool", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("could not be confirmed");
  await expect(page.getByLabel("Text to analyze")).toHaveValue("Preserve this text");
  expect(writes).toBe(1);
});

test("a late history response cannot erase a newly confirmed run", async ({ page }, testInfo) => {
  let release!: () => void;
  const pending = new Promise<void>(resolve => { release = resolve; });
  await page.route("**/api/v1/agents/runs{,?*}", async route => {
    if (route.request().method() === "POST") return reply(route, {
      id: "synthetic-new-run", goal: "Fresh result", status: "completed", created_at: "2026-10-16T10:00:00Z",
      steps: [{ status: "completed", tool: "text_stats", result: { words: 2, characters: 12 } }],
    }, 201);
    await pending;
    await reply(route, { items: [] });
  });
  try {
    await page.goto("/agents");
    await expect(page.getByRole("status")).toContainText("Loading run history");
    await page.getByLabel("Text to analyze").fill("Fresh result");
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Run tool", exact: true }).click();
    await expect(page.locator(".tool-results")).toContainText("Words2");
    release();
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(page.locator(".tool-results")).toContainText("Words2");
    await page.screenshot({ path: testInfo.outputPath("agents-results.png"), fullPage: true });
  } finally { release(); }
});

test("the exact input label remains stable while typing and changing system appearance", async ({ page }) => {
  await page.route("**/api/v1/agents/runs{,?*}", route => reply(route, { items: [] }));
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/agents", { waitUntil: "networkidle" });
  const draft = page.getByLabel("Text to analyze", { exact: true });
  await draft.fill("Unsent synthetic draft");
  // Resolve the same exact label again after React updates the controlled value.
  await expect(draft).toHaveCount(1);
  await draft.focus();
  const requests: string[] = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) requests.push(request.url());
  });
  for (const mode of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme: mode });
    await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe(mode);
    await expect(draft).toHaveValue("Unsent synthetic draft");
    await expect(draft).toBeFocused();
    await expect(page.getByRole("textbox", { name: "Text to analyze", exact: true })).toHaveCount(1);
  }
  expect(requests).toEqual([]);
  expect(await page.evaluate(() => Object.keys(localStorage).filter(key => /theme|appearance/i.test(key)))).toEqual([]);
});
