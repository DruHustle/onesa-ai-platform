import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import path from "node:path";
import fs from "node:fs";

const root = path.resolve(__dirname, "../../../..");
const password = "twin-synthetic-fixture-only-123!";
const owned = new WeakMap<Page, string>();
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
    throw new Error("Twin synthetic browser fixtures are loopback-only");
  const email = `twin-${randomUUID()}@example.com`;
  const response = await page.request.post("/api/v1/auth/register", {
    headers: { Origin: origin },
    data: { email, password, display_name: "Synthetic twin reviewer" },
  });
  expect(response.status()).toBe(201);
  owned.set(page, email);
}
async function seeded(page: Page, origin: string) {
  await register(page, origin);
  await page.goto("/industrial/twins");
  await page
    .getByRole("button", { name: "Load isolated pump demonstration" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Demo pump 01", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("equipment-model-loaded")).toBeVisible();
  await expect
    .poll(async () =>
      Number(
        await page
          .getByTestId("equipment-model-loaded")
          .getAttribute("data-draw-calls"),
      ),
    )
    .toBeGreaterThan(0);
}
async function mqtt(page: Page, origin: string) {
  const catalog = await (
    await page.request.get("/api/v1/twins/catalog")
  ).json();
  const asset = catalog.assets[0],
    bearing = asset.definition.components.find(
      (c: { external_id: string }) => c.external_id === "bearing",
    );
  const response = await page.request.post(
    `/api/v1/twins/assets/${asset.id}/sources`,
    {
      headers: await headers(page, origin),
      data: {
        name: "Actual MQTT simulated fixture",
        mode: "simulated",
        bindings: [
          {
            tag: "vibration",
            component_id: bearing.id,
            metric: "vibration",
            unit: "mm/s",
            sample_seconds: 1,
            stale_seconds: 10,
            high: 5,
            hysteresis: 1,
          },
        ],
      },
    },
  );
  expect(response.status()).toBe(201);
  const source = await response.json();
  const output = execFileSync(
    path.join(root, ".venv/bin/python"),
    ["-m", "app.twin_mqtt_fixture"],
    {
      cwd: path.join(root, "onesa-ai-platform-backend"),
      input: JSON.stringify({
        api_origin: origin,
        source_id: source.id,
        source_token: source.ingestion_token,
        broker_port: Number(process.env.ONESA_TWIN_MQTT_PORT || 18883),
      }),
      timeout: 30000,
      encoding: "utf8",
      stdio: ["pipe", "pipe", "pipe"],
    },
  );
  const receipt = JSON.parse(output);
  expect(receipt.platform_accepted).toBe(4);
  expect(receipt.protocol).toBe("MQTT 3.1.1");
  return { asset, bearing, source: { id: source.id }, receipt };
}

const requests = new WeakMap<
  Page,
  { origin: string; path: string; method: string; allowed: boolean }[]
>();
test.beforeEach(async ({ page, context, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  const entries: {
    origin: string;
    path: string;
    method: string;
    allowed: boolean;
  }[] = [];
  requests.set(page, entries);
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    const allowed =
      !["http:", "https:"].includes(url.protocol) || url.origin === origin;
    entries.push({
      origin: url.origin,
      path: url.pathname,
      method: route.request().method(),
      allowed,
    });
    return allowed ? route.continue() : route.abort("blockedbyclient");
  });
});
test.afterEach(async ({ page, baseURL }, testInfo) => {
  const network = requests.get(page) || [];
  await testInfo.attach("standalone-network", {
    body: JSON.stringify({
      freshBrowserContext: true,
      peerPairing: false,
      requests: network,
    }),
    contentType: "application/json",
  });
  expect(network.filter((request) => !request.allowed)).toEqual([]);
  const email = owned.get(page);
  if (!email) return;
  const login = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: new URL(baseURL!).origin },
    data: { email, password },
  });
  expect(login.status()).toBe(200);
  const result = await page.request.post("/api/v1/account/delete", {
    headers: await headers(page, new URL(baseURL!).origin),
    data: { current_password: password, confirmation: "DELETE MY ACCOUNT" },
  });
  expect(result.status()).toBe(204);
});

test("actual pump: GLB, MQTT, history, grounded tools, saved inspection and reload", async ({
  page,
  baseURL,
  browserName,
}, testInfo) => {
  test.setTimeout(120000);
  const origin = new URL(baseURL!).origin;
  await seeded(page, origin);
  const telemetry = await mqtt(page, origin);
  await page.getByRole("button", { name: "Bearing", exact: true }).click();
  await page.getByRole("tab", { name: "Details", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "3 mm/s",
    { timeout: 12000 },
  );
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Load history", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "History" })).toContainText(
    "threshold crossing",
  );
  await expect(page.getByRole("tabpanel", { name: "History" })).toContainText(
    "threshold recovery",
  );
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  await page
    .getByText("Onesa illustrative pump maintenance — sections 1–3", {
      exact: true,
    })
    .click();
  await expect(page.getByRole("tabpanel", { name: "Documents" })).toContainText(
    "Section 2 — Bearing vibration inspection",
  );
  await page
    .getByRole("button", { name: "Inspect selected evidence", exact: true })
    .click();
  await expect(page.getByLabel("Equipment evidence answer")).toContainText(
    "deterministic evidence",
  );
  await expect(page.getByLabel("Equipment evidence answer")).toContainText(
    "Procedure evidence",
  );
  await page
    .getByRole("button", {
      name: "Save evidence-backed inspection checklist",
      exact: true,
    })
    .click();
  await expect(
    page.getByText(/Equipment inspection checklist ·/),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText(/Equipment inspection checklist ·/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Bearing", exact: true }).click();
  await page.getByRole("tab", { name: "Details", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "stale",
    { timeout: 20000 },
  );
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "disconnected",
  );
  await page
    .getByLabel("Equipment", { exact: true })
    .selectOption({ label: "Demo pump 02 · ONESA-DEMO-PUMP-02" });
  await page.getByRole("button", { name: "Bearing", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "No bound measurements",
  );
  await page
    .getByLabel("Equipment", { exact: true })
    .selectOption(telemetry.asset.id);
  await page.getByRole("tab", { name: "Model", exact: true }).click();
  const canvas = page.locator("canvas");
  await expect(canvas).toBeVisible();
  await expect
    .poll(() =>
      canvas.evaluate(
        (element: HTMLCanvasElement) =>
          element.width > 300 &&
          Math.abs(element.width - element.clientWidth) <= 1,
      ),
    )
    .toBe(true);
  const pixels = await canvas.evaluate((element: HTMLCanvasElement) => {
    const gl = element.getContext("webgl2");
    if (!gl) return { webgl: false };
    const extension = gl.getExtension("WEBGL_debug_renderer_info");
    return {
      webgl: true,
      renderer: extension
        ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL)
        : gl.getParameter(gl.RENDERER),
      width: element.width,
      height: element.height,
    };
  });
  expect(pixels.webgl).toBe(true);
  const evidenceDirectory = process.env.ONESA_TWIN_EVIDENCE_DIRECTORY;
  if (evidenceDirectory) {
    fs.mkdirSync(evidenceDirectory, { recursive: true });
    await page.screenshot({
      path: path.join(evidenceDirectory, `${browserName}-pump-desktop.png`),
    });
    fs.writeFileSync(
      path.join(evidenceDirectory, `${browserName}-protocol.json`),
      JSON.stringify(
        {
          browser: browserName,
          viewport: page.viewportSize(),
          renderer: pixels,
          protocol: telemetry.receipt,
          firstSettledFrameMs: await page
            .getByTestId("equipment-model-loaded")
            .getAttribute("data-first-settled-frame-ms"),
          network: requests.get(page),
          coldModelLoadMs: await page
            .getByTestId("equipment-model-loaded")
            .getAttribute("data-load-ms"),
        },
        null,
        2,
      ),
    );
  }
  await testInfo.attach("actual-protocol-and-renderer", {
    body: JSON.stringify({ protocol: telemetry.receipt, renderer: pixels }),
    contentType: "application/json",
  });
});

test("actual viewer controls, context loss, responsive themes and navigation", async ({
  page,
  baseURL,
  browserName,
}) => {
  test.setTimeout(120000);
  await seeded(page, new URL(baseURL!).origin);
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 820, height: 1180 },
    { width: 390, height: 844 },
  ])
    for (const colorScheme of ["light", "dark"] as const) {
      await page.setViewportSize(viewport);
      await page.emulateMedia({ colorScheme });
      await page.getByRole("tab", { name: "Model", exact: true }).click();
      await page.getByRole("button", { name: "Impeller", exact: true }).click();
      await page
        .getByRole("button", { name: "Focus selected", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Transparent surroundings", exact: true })
        .click();
      await page.getByRole("button", { name: "Isolate", exact: true }).click();
      await expect(
        page.getByRole("button", { name: "Isolate", exact: true }),
      ).toHaveAttribute("aria-pressed", "true");
      await page.getByRole("button", { name: "Isolate", exact: true }).click();
      await page
        .getByRole("button", { name: "Hide selected", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Show selected", exact: true }),
      ).toBeVisible();
      await page
        .getByRole("button", { name: "Show selected", exact: true })
        .click();
      await page
        .getByRole("button", { name: "Save viewpoint", exact: true })
        .click();
      await expect(
        page.getByRole("button", { name: "Viewpoint 1", exact: true }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      const violations = (
        await new AxeBuilder({ page }).analyze()
      ).violations.filter((v) =>
        ["critical", "serious"].includes(v.impact || ""),
      );
      expect(violations).toEqual([]);
      const evidenceDirectory = process.env.ONESA_TWIN_EVIDENCE_DIRECTORY;
      if (evidenceDirectory)
        await page.screenshot({
          path: path.join(
            evidenceDirectory,
            `${browserName}-${viewport.width}-${colorScheme}.png`,
          ),
        });
    }
  await page
    .locator("canvas")
    .evaluate((element: HTMLCanvasElement) =>
      element
        .getContext("webgl2")
        ?.getExtension("WEBGL_lose_context")
        ?.loseContext(),
    );
  await expect(
    page.getByRole("alert").filter({ hasText: "Graphics context lost" }),
  ).toContainText("Graphics context lost");
  await page.getByRole("tab", { name: "Details", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "Impeller",
  );
  await page.getByRole("link", { name: "Knowledge", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your knowledge", exact: true }),
  ).toBeVisible();
});

test("manual setup and actual AASX preview, explicit mapping review and activation", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(120000);
  await register(page, new URL(baseURL!).origin);
  await page.goto("/industrial/twins");
  const fixture = await page.request.get(
    "/api/v1/twins/demo-fixtures/pump.aasx",
  );
  expect(fixture.ok()).toBe(true);
  await page
    .getByLabel("Attach a model, AAS package or source document")
    .setInputFiles({
      name: "pump.aasx",
      mimeType: "application/octet-stream",
      buffer: await fixture.body(),
    });
  await expect(
    page.getByRole("heading", { name: "Review pump.aasx", exact: true }),
  ).toBeVisible();
  const preview = page.getByLabel("Import preview");
  await preview
    .getByLabel("Installed serial number", { exact: true })
    .fill("AASX-BROWSER-01");
  await preview
    .getByLabel("Embedded geometry to review")
    .selectOption({ label: "aasx/files/pump.glb" });
  await preview.getByLabel(/Index embedded manuals in my Knowledge/).check();
  await preview
    .getByRole("button", {
      name: "Commit reviewed equipment import",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "IllustrativePump", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Saved setup stage: mapping", { exact: true }),
  ).toBeVisible();
  // Import proposals remain inactive. Confirm mapping/scale through the explicit revision review.
  const detail = await (await page.request.get("/api/v1/twins/catalog")).json();
  const value = await (
    await page.request.get(`/api/v1/twins/assets/${detail.assets[0].id}`)
  ).json();
  expect(value.asset.active_model_id).toBeNull();
  expect(value.documents.map((d: { title: string }) => d.title)).toContain(
    "maintenance.txt",
  );
  await page
    .getByLabel("I reviewed the imported mapping and model scale.")
    .check();
  await page
    .getByRole("button", {
      name: "Review imported model mapping and scale",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("button", {
      name: "Activate reviewed workspace",
      exact: true,
    }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Activate reviewed workspace", exact: true })
    .click();
  await expect(
    page.getByText("Saved setup stage: active", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "IllustrativePump", exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  await expect(
    page.getByText("maintenance.txt", { exact: true }),
  ).toBeVisible();
});

test("cold independent local simulator and saved work survive source outage", async ({
  page,
  baseURL,
}) => {
  test.setTimeout(90000);
  await seeded(page, new URL(baseURL!).origin);
  await page.getByRole("button", { name: "Bearing", exact: true }).click();
  await page
    .getByRole("button", { name: "Run local simulated cycle", exact: true })
    .click();
  await page.getByRole("tab", { name: "Details", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "3 mm/s",
  );
  await page
    .getByRole("button", { name: "Pause local simulated source", exact: true })
    .click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "stale",
  );
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "disconnected",
  );
  expect((await page.request.get("/ready")).status()).toBe(200);
  await page.getByText("Component annotations", { exact: true }).click();
  await page
    .getByLabel("Inspection annotation")
    .fill("Onesa-local inspection survives optional source loss.");
  await page
    .getByRole("button", { name: "Save annotation", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Save evidence-backed inspection checklist",
      exact: true,
    })
    .click();
  await expect(
    page.getByText(/Equipment inspection checklist ·/),
  ).toBeVisible();
  if (process.env.ONESA_TWIN_E2E_CONTROL === "native") {
    execFileSync(
      path.join(root, ".venv/bin/python"),
      [path.join(root, "scripts/twins/restart_fixture_api.py")],
      { cwd: root, timeout: 20000, stdio: "pipe" },
    );
  } else if (
    process.env.CI === "true" ||
    process.env.ONESA_TWIN_E2E_CONTROL === "compose"
  ) {
    execFileSync(
      "docker",
      [
        "compose",
        "-f",
        "compose.yaml",
        "-f",
        "compose.twins-demo.yaml",
        "restart",
        "--no-deps",
        "api",
      ],
      { cwd: root, timeout: 25000, stdio: "pipe" },
    );
  } else
    throw new Error(
      "Use an explicitly isolated native/Compose fixture for the required API restart check",
    );
  await expect
    .poll(
      async () => {
        try {
          return (await page.request.get("/ready", { timeout: 2000 })).status();
        } catch {
          return 0;
        }
      },
      { timeout: 30000 },
    )
    .toBe(200);
  await page.reload();
  await expect(page.getByTestId("equipment-model-loaded")).toBeVisible();
  await expect(
    page.getByText(/Equipment inspection checklist ·/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Bearing", exact: true }).click();
  await page.getByRole("tab", { name: "Details", exact: true }).click();
  await page.getByText("Component annotations", { exact: true }).click();
  await expect(
    page.getByText("Onesa-local inspection survives optional source loss.", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Simulate normal", exact: true })
    .click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "2 mm/s",
  );
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await page.getByRole("button", { name: "Load history", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "History" })).toContainText(
    "threshold crossing",
  );
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  await page
    .getByText("Onesa illustrative pump maintenance — sections 1–3", {
      exact: true,
    })
    .click();
  await expect(page.getByRole("tabpanel", { name: "Documents" })).toContainText(
    "Section 2 — Bearing vibration inspection",
  );
});
