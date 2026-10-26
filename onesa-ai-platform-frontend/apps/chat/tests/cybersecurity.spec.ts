import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { randomUUID } from "node:crypto";

const password = "security-synthetic-fixture-only-123!";
const root = "/api/v1/cybersecurity";
const identities = new WeakMap<Page, string>();
async function headers(page: Page, origin: string) {
  return {
    Origin: origin,
    "X-CSRF-Token":
      (await page.context().cookies(origin)).find(
        (c) => c.name === "onesa_csrf",
      )?.value || "",
  };
}
async function register(page: Page, origin: string) {
  if (!["127.0.0.1", "localhost", "[::1]"].includes(new URL(origin).hostname))
    throw Error("Security browser fixtures are loopback-only");
  const email = `security-${randomUUID()}@example.com`;
  const response = await page.request.post("/api/v1/auth/register", {
    headers: { Origin: origin },
    data: { email, password, display_name: "Synthetic security reviewer" },
  });
  expect(response.status()).toBe(201);
  identities.set(page, email);
}
function evidence(namespace: string, index: number, mapped = true) {
  return {
    schemaVersion: "ot-security-evidence/v1",
    producerNamespace: namespace,
    sourceEventId: `browser-observation-${index}`,
    occurredAt: new Date().toISOString(),
    mode: "simulated",
    scenarioRunId: "explicit-browser-demonstration",
    eventType: "auth.authentication_failed",
    assetRef: mapped
      ? { namespace: "maintenance", assetId: "gateway-01", componentId: null }
      : null,
    summary: "Synthetic rejected access observation; not a real incident",
    quality: "good",
    producerVersion: "browser-fixture/1",
    attributes: {
      service: "isolated-test",
      outcome: "denied",
      reasonCode: "SYNTHETIC_REJECTION",
    },
  };
}
async function prepared(page: Page, origin: string) {
  await register(page, origin);
  const h = await headers(page, origin);
  const a = await page.request.post(root + "/assets", {
    headers: h,
    data: {
      name: "Synthetic reviewed gateway",
      identity: "gateway-01",
      zone: "Isolated test",
      criticality: "high",
      review_note: "Explicit synthetic inventory review",
    },
  });
  expect(a.status()).toBe(201);
  const asset = await a.json();
  const s = await page.request.post(root + "/sources", {
    headers: h,
    data: {
      name: "Synthetic local source",
      namespace: "onesa-browser-fixture",
      modes: ["simulated"],
      expected_interval_seconds: 60,
      review_note: "Explicit simulated evidence source",
    },
  });
  expect(s.status()).toBe(201);
  const source = await s.json();
  const m = await page.request.post(root + `/sources/${source.id}/mappings`, {
    headers: h,
    data: {
      asset_id: asset.id,
      namespace: "maintenance",
      external_asset: "gateway-01",
      review_note: "Reviewed synthetic local asset mapping",
    },
  });
  expect(m.status()).toBe(201);
  const i = await page.request.post(root + `/sources/${source.id}/imports`, {
    headers: h,
    data: {
      events: Array.from({ length: 5 }, (_, i) =>
        evidence(source.namespace, i),
      ),
    },
  });
  expect(i.status()).toBe(200);
  const data = await (
    await page.request.get(root + "/workspace?mode=simulated")
  ).json();
  return { asset, source, finding: data.findings[0] };
}
test.afterEach(async ({ page, baseURL }) => {
  if (!identities.has(page)) return;
  const response = await page.request.post("/api/v1/account/delete", {
    headers: await headers(page, baseURL!),
    data: { current_password: password, confirmation: "DELETE MY ACCOUNT" },
  });
  expect(response.status()).toBe(204);
  identities.delete(page);
});

test("actual setup import asset finding decisions and reload are independent of models", async ({
  page,
  baseURL,
}) => {
  await register(page, baseURL!);
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("/industrial/cybersecurity");
  await expect(
    page.getByRole("heading", { name: "Cybersecurity", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Cybersecurity", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Evidence mode").selectOption("simulated");
  const nav = page.getByRole("navigation", { name: "Cybersecurity views" });
  await nav.getByRole("button", { name: "Assets", exact: true }).click();
  await page
    .getByLabel("Asset name", { exact: true })
    .fill("Synthetic reviewed gateway");
  await page.getByLabel("Stable local identity").fill("gateway-01");
  await page.getByLabel("Reviewed zone").fill("Isolated maintenance");
  await page
    .getByRole("combobox", { name: "Criticality", exact: true })
    .selectOption("high");
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Owner reviewed explicitly synthetic gateway inventory");
  await page
    .getByRole("button", { name: "Register asset", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Saved");
  await nav.getByRole("button", { name: "Sources", exact: true }).click();
  await page
    .getByLabel("Source name", { exact: true })
    .fill("Browser-owned collector");
  await page
    .getByLabel("Producer namespace", { exact: true })
    .fill("onesa-browser-fixture");
  await page
    .getByLabel("Source review note")
    .fill("Reviewed bounded synthetic collector source");
  await page.getByRole("button", { name: "Create scoped source" }).click();
  await expect(
    page.getByRole("heading", { name: "One-time scoped credential" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Dismiss credential" }).click();
  await page
    .getByRole("combobox", { name: "Local reviewed asset", exact: true })
    .selectOption({ label: "Synthetic reviewed gateway" });
  await page.getByLabel("External asset namespace").fill("maintenance");
  await page
    .getByLabel("External asset reference", { exact: true })
    .fill("gateway-01");
  await page
    .getByLabel("Mapping review note")
    .fill("Reviewed explicit synthetic source-to-asset mapping");
  await page
    .getByRole("button", { name: "Review mapping", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Saved");
  await page.getByLabel("Evidence batch", { exact: true }).fill(
    JSON.stringify({
      events: Array.from({ length: 5 }, (_, i) =>
        evidence("onesa-browser-fixture", i),
      ),
    }),
  );
  await page
    .getByRole("button", { name: "Import evidence", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Imported 5");
  await nav.getByRole("button", { name: "Findings", exact: true }).click();
  await page
    .getByRole("button", { name: "auth.authentication failed", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Selected finding" }),
  ).toContainText("compromise is not established");
  await page
    .getByRole("button", { name: "Follow asset: Synthetic reviewed gateway" })
    .click();
  await expect(
    page.getByRole("region", { name: "Selected asset" }),
  ).toContainText("Reviewed identity: gateway-01");
  await page
    .getByRole("region", { name: "Selected asset" })
    .getByRole("button", { name: /auth.authentication_failed/ })
    .click();
  await page
    .getByRole("button", { name: "Create investigation", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Selected investigation" }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Decision", exact: true })
    .selectOption("acknowledge");
  await page
    .getByLabel("Decision note")
    .fill("Reviewed explicit synthetic rejection evidence");
  await page.getByRole("button", { name: "Record decision" }).click();
  await expect(
    page.getByRole("region", { name: "Selected investigation" }),
  ).toContainText("Revision 2");
  const caseId = (
    await (await page.request.get(root + "/workspace?mode=simulated")).json()
  ).investigations[0].id;
  await page.reload();
  await nav
    .getByRole("button", { name: "Investigations", exact: true })
    .click();
  await page
    .getByRole("button", { name: /Review auth.authentication_failed/ })
    .click();
  await expect(
    page.getByRole("region", { name: "Selected investigation" }),
  ).toContainText("Reviewed explicit synthetic rejection evidence");
  await page
    .getByRole("combobox", { name: "Decision", exact: true })
    .selectOption("reopen");
  await page
    .getByLabel("Decision note")
    .fill("Explicitly reopen for a further human review");
  await page.getByRole("button", { name: "Record decision" }).click();
  await expect(
    page.getByRole("region", { name: "Selected investigation" }),
  ).toContainText("Revision 3");
  await page.getByRole("button", { name: "Prepare checklist" }).click();
  await expect(page.getByLabel("Investigation checklist")).toContainText(
    "deterministic",
  );
  const persisted = await (
    await page.request.get(root + `/investigations/${caseId}`)
  ).json();
  expect(
    persisted.investigation.snapshot.finding.details.evidence,
  ).toHaveLength(5);
  expect(persisted.evidence.history).toHaveLength(3);
  expect(await page.locator("canvas").count()).toBe(0);
  expect(
    requests.filter((url) => /\.glb(?:\?|$)|smart-factory|mqtt:\/\//.test(url)),
  ).toEqual([]);
  await page.getByLabel("Evidence mode").selectOption("live");
  await nav.getByRole("button", { name: "Findings", exact: true }).click();
  await expect(
    page.getByText("No findings in this mode.", { exact: false }),
  ).toBeVisible();
});

test("rendered responsive themes keyboard evidence and inert hostile text", async ({
  page,
  baseURL,
}, testInfo) => {
  const { source } = await prepared(page, baseURL!);
  const h = await headers(page, baseURL!);
  const hostile = {
    ...evidence(source.namespace, 50),
    summary: "<img src=x onerror=alert(1)> Untrusted imported text",
  };
  expect(
    (
      await page.request.post(root + `/sources/${source.id}/imports`, {
        headers: h,
        data: { events: [hostile] },
      })
    ).status(),
  ).toBe(200);
  for (const colorScheme of ["light", "dark"] as const)
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 960 });
      await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
      await page.goto("/industrial/cybersecurity?mode=simulated");
      await expect(
        page.getByRole("heading", { name: "Cybersecurity", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Review findings", exact: true }),
      ).toBeVisible();
      const ax = await new AxeBuilder({ page }).analyze();
      expect(ax.violations).toEqual([]);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
      ).toBe(true);
      await page.screenshot({
        path: testInfo.outputPath(
          `cybersecurity-overview-${colorScheme}-${width}.png`,
        ),
        fullPage: true,
      });
      await page
        .getByRole("navigation", { name: "Cybersecurity views" })
        .getByRole("button", { name: "Events", exact: true })
        .click();
      await page
        .getByRole("button", { name: hostile.summary, exact: true })
        .click();
      await expect(
        page.getByRole("region", { name: "Selected event" }),
      ).toContainText(hostile.summary);
      expect(await page.locator('img[src="x"]').count()).toBe(0);
      await page.screenshot({
        path: testInfo.outputPath(
          `cybersecurity-events-${colorScheme}-${width}.png`,
        ),
        fullPage: true,
      });
    }
  await page
    .getByRole("navigation", { name: "Cybersecurity views" })
    .getByRole("button", { name: "Findings", exact: true })
    .focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Deterministic findings" }),
  ).toBeVisible();
});

test("current owner boundaries and source revocation hold through the real gateway", async ({
  page,
  baseURL,
}) => {
  const { source, asset, finding } = await prepared(page, baseURL!);
  const h = await headers(page, baseURL!);
  const denied = await page.request.post(root + "/assets", {
    headers: { Origin: baseURL! },
    data: {
      name: "Rejected",
      identity: "never-created",
      zone: "test",
      criticality: "unknown",
      review_note: "No valid CSRF proof was supplied",
    },
  });
  expect(denied.status()).toBe(403);
  const ingested = await page.request.post(root + "/ingest", {
    headers: { Authorization: `Bearer ${source.ingestion_token}` },
    data: { events: [evidence(source.namespace, 99)] },
  });
  expect(ingested.status()).toBe(200);
  expect(
    (
      await page.request.post(root + `/sources/${source.id}/revoke`, {
        headers: h,
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await page.request.post(root + "/ingest", {
        headers: { Authorization: `Bearer ${source.ingestion_token}` },
        data: { events: [evidence(source.namespace, 100)] },
      })
    ).status(),
  ).toBe(401);
  const originalEmail = identities.get(page)!;
  await page.context().clearCookies();
  await register(page, baseURL!);
  await page.goto(
    `/industrial/cybersecurity?mode=simulated&view=Findings&finding=${finding.id}`,
  );
  await expect(
    page.getByText("No findings in this mode.", { exact: false }),
  ).toBeVisible();
  for (const path of [
    `/assets/${asset.id}`,
    `/findings/${finding.id}`,
    `/export?source_id=${source.id}`,
  ])
    expect((await page.request.get(root + path)).status()).toBe(404);
  // Remove only both accounts created by this loopback test; no shared fixtures are touched.
  expect(
    (
      await page.request.post("/api/v1/account/delete", {
        headers: await headers(page, baseURL!),
        data: { current_password: password, confirmation: "DELETE MY ACCOUNT" },
      })
    ).status(),
  ).toBe(204);
  expect(
    (
      await page.request.post("/api/v1/auth/login", {
        headers: { Origin: baseURL! },
        data: { email: originalEmail, password },
      })
    ).status(),
  ).toBe(200);
  identities.set(page, originalEmail);
});

test("optional owned Twin focus preserves explosion state and returns to security evidence", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(90000);
  const { source } = await prepared(page, baseURL!),
    h = await headers(page, baseURL!);
  const demo = await page.request.post("/api/v1/twins/demo", { headers: h });
  expect(demo.status()).toBe(201);
  const installed = (await demo.json()).assets[0];
  const component = installed.definition.components.find(
    (c: { renderable?: boolean; parent_id: string | null }) =>
      c.renderable !== false && c.parent_id,
  );
  expect(component).toBeTruthy();
  const created = await page.request.post(root + "/assets", {
    headers: h,
    data: {
      name: "Mapped synthetic pump",
      identity: "installed-pump-01",
      zone: "Isolated test",
      criticality: "high",
      review_note: "Reviewed installed asset and component association",
      twin_asset_id: installed.id,
      twin_component_id: component.id,
    },
  });
  expect(created.status()).toBe(201);
  const asset = await created.json();
  expect(
    (
      await page.request.post(root + `/sources/${source.id}/mappings`, {
        headers: h,
        data: {
          asset_id: asset.id,
          namespace: "maintenance",
          external_asset: "installed-pump",
          review_note: "Reviewed independent local equipment mapping",
        },
      })
    ).status(),
  ).toBe(201);
  const observations = Array.from({ length: 5 }, (_, index) => ({
    ...evidence(source.namespace, 200 + index),
    assetRef: {
      namespace: "maintenance",
      assetId: "installed-pump",
      componentId: null,
    },
  }));
  expect(
    (
      await page.request.post(root + `/sources/${source.id}/imports`, {
        headers: h,
        data: { events: observations },
      })
    ).status(),
  ).toBe(200);
  await page.goto(
    `/industrial/twins?asset=${installed.id}&component=${component.id}`,
  );
  const rendered = page.getByTestId("equipment-model-loaded");
  await expect(rendered).toBeVisible({ timeout: 30000 });
  await page.getByRole("button", { name: "Explode", exact: true }).click();
  await expect(
    page.getByRole("slider", { name: "Explosion percent" }),
  ).toHaveValue("100");
  await expect(rendered).toHaveAttribute("data-inspection-settled", "true", {
    timeout: 15000,
  });
  await page.getByText("Security evidence (optional)", { exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Highlight mapped security components" })
    .check();
  await page.getByRole("button", { name: "Focus mapped component" }).click();
  await expect(
    page
      .getByRole("complementary", { name: "Equipment components" })
      .getByRole("button", { name: component.name, exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("slider", { name: "Explosion percent" }),
  ).toHaveValue("100");
  await page
    .getByRole("link", {
      name: /auth.authentication failed · medium · simulated/,
    })
    .click();
  await expect(
    page.getByRole("region", { name: "Selected finding" }),
  ).toContainText("compromise is not established");
  await expect(
    page.getByRole("button", { name: "Follow asset: Mapped synthetic pump" }),
  ).toBeVisible();
});
