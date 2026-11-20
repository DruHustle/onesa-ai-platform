import {test, expect} from "@playwright/test";

// Synthetic loopback API fixtures: this is UI contract coverage, not live inference.
test.beforeEach(async ({page, baseURL}) => {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL!).hostname)) {
    throw new Error("Loopback fixture only");
  }
  let saved: Record<string, unknown> | null = null;
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let data: unknown = {};
    if (path === "/api/v1/auth/me") {
      data = {id: "synthetic-work-owner", display_name: "Synthetic Work User"};
    } else if (path === "/api/v1/documentation/access") {
      data = {engineering: false};
    } else if (path === "/api/v1/agents/tools") {
      data = {items: [
        {name: "text_stats", effect: "local computation", schema: {
          properties: {text: {type: "string"}}, required: ["text"],
        }},
        {name: "knowledge_search", effect: "read-only owned evidence", schema: {
          properties: {query: {type: "string"}, document_ids: {type: "array"}},
          required: ["query"],
        }},
      ]};
    } else if (path === "/api/v1/agents/runs" && route.request().method() === "POST") {
      const request = route.request().postDataJSON();
      if (!request.allowed_tools.includes("text_stats")) throw Error("Missing explicit tool grant");
      saved = {
        id: request.id, goal: request.goal, status: "completed",
        created_at: new Date().toISOString(), steps: [
          {tool: "text_stats", status: "completed", result: {words: 3, characters: 13}},
        ],
      };
      data = saved;
    } else if (path === "/api/v1/agents/runs") {
      data = {items: saved ? [saved] : [], next_cursor: null};
    } else {
      await route.fulfill({status: 404, contentType: "application/json", body: "{}"});
      return;
    }
    await route.fulfill({contentType: "application/json", body: JSON.stringify(data)});
  });
});

test("Work requires a tool grant and shows saved results", async ({page}) => {
  await page.goto("/work");
  await expect(page.getByRole("heading", {name: "Work", exact: true})).toBeVisible();
  const run = page.getByRole("button", {name: "Approve tools & run"});
  await page.getByLabel("What should Onesa AI work on?").fill("Count these words");
  await expect(run).toBeDisabled();
  await page.getByLabel(/Text Stats/).check();
  await expect(run).toBeEnabled();
  await run.click();
  await expect(page.getByRole("heading", {name: "Run result"})).toBeVisible();
  await expect(page.getByText('"words": 3')).toBeVisible();
});

test("Plugins are discovered from server permissions and link to Work", async ({page}) => {
  await page.goto("/plugins");
  await expect(page.getByRole("heading", {name: "Plugins", exact: true})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Your Knowledge"})).toBeVisible();
  await expect(page.getByRole("heading", {name: "Knowledge Search"})).toBeVisible();
  await expect(page.getByText("External account connection and plugin installation are not enabled")).toBeVisible();
  const link = page.getByRole("link", {name: "Use in Work"}).first();
  await link.click();
  await expect(page).toHaveURL(/\/work$/);
});
