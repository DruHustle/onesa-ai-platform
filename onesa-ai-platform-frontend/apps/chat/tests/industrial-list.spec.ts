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
