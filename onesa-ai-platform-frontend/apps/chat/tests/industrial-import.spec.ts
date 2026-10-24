import {test, expect} from "@playwright/test";
import {readFile} from "node:fs/promises";
import {resolve} from "node:path";
import {randomUUID} from "node:crypto";

test("actual synthetic JSON import, read-only grant, abstention, draft, reopen and export", async ({page, context, baseURL}, info) => {
  const origin = new URL(baseURL!).origin;
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(origin).hostname)) throw Error("Isolated loopback fixtures only");
  const ready = await page.request.get("/ready");
  expect((await ready.json()).backend).toBe("mock");
  const password = "synthetic-import-browser-only-123!";
  const register = await page.request.post("/api/v1/auth/register", {headers: {Origin: origin},
    data: {email: `import-${randomUUID()}@example.com`, password, display_name: "Synthetic importer"}});
  expect(register.status()).toBe(201);
  const csrf = () => context.cookies(origin).then(cookies => cookies.find(cookie => cookie.name === "onesa_csrf")?.value || "");
  try {
    const sample = await readFile(resolve(__dirname, "../../../../onesa-ai-platform-backend/tests/fixtures/industrial-import-v1.json"));
    await page.goto("/industrial");
    await page.getByLabel("Versioned evidence bundle (.json, up to 512 KiB)").setInputFiles({name: "synthetic-input.json", mimeType: "application/json", buffer: sample});
    await page.getByRole("button", {name: "Validate and preview import", exact: true}).click();
    await expect(page.getByText(/Known downtime: 300 seconds/)).toBeVisible();
    await page.getByRole("button", {name: "Save imported investigation", exact: true}).click();
    await expect(page.getByRole("heading", {name: "2. Observed evidence", exact: true})).toBeVisible();
    await expect(page.getByRole("button", {name: "Read saved investigation facts", exact: true})).toBeDisabled();
    await page.getByLabel("Allow read-only access to this investigation for this run").check();
    await page.getByRole("button", {name: "Read saved investigation facts", exact: true}).click();
    await expect(page.getByText(/read-only tool returned the permitted saved facts/)).toBeVisible();
    await page.getByRole("button", {name: "Run investigation", exact: true}).click();
    await expect(page.getByText(/imported source meaning has not been evaluated/)).toBeVisible();
    await page.getByRole("button", {name: "Create internal draft", exact: true}).click();
    await page.getByLabel("Draft text", {exact: true}).fill("Synthetic draft with 300 seconds known downtime. Independent domain review is pending.");
    await page.getByRole("button", {name: "Save internal draft", exact: true}).click();
    await page.reload();
    await page.getByRole("button", {name: /synthetic-separator-17.*completed/}).click();
    await expect(page.getByLabel("Draft text", {exact: true})).toHaveValue(/Independent domain review is pending/);
    const exported = await page.request.post("/api/v1/account/export", {headers: {Origin: origin, "X-CSRF-Token": await csrf()}, data: {current_password: password}});
    expect(exported.status()).toBe(200);
    const record = (await exported.json()).industrial_investigations[0];
    expect(record.payload.facts.known_downtime_seconds).toBe(300);
    expect(record.payload.review).toBeNull();
    expect(record.payload.generation_attempts[0].cost).toBeNull();
    await page.screenshot({path: info.outputPath("synthetic-import-reopened.png"), fullPage: true});
  } finally {
    const deleted = await page.request.post("/api/v1/account/delete", {headers: {Origin: origin, "X-CSRF-Token": await csrf()}, data: {current_password: password, confirmation: "DELETE MY ACCOUNT"}});
    expect(deleted.status()).toBe(204);
  }
});
