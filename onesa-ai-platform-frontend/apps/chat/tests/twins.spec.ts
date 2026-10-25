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
  page.setDefaultTimeout(10000);
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
    .getByText("Onesa illustrative pump maintenance — sections 1–5", {
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
    { timeout: 20000 },
  );
  // The actual optional MQTT adapter/publisher have stopped. A separate local
  // acquisition path remains usable without relabeling that old source healthy.
  expect((await page.request.get("/ready")).status()).toBe(200);
  await page
    .getByRole("button", { name: "Simulate normal", exact: true })
    .click();
  await expect(page.getByRole("tabpanel", { name: "Details" })).toContainText(
    "2 mm/s",
  );
  const afterOutage = await (
    await page.request.get(
      `/api/v1/twins/assets/${telemetry.asset.id}?mode=simulated`,
    )
  ).json();
  expect(
    afterOutage.state.some(
      (s: { source_id: string; connection: string }) =>
        s.source_id === telemetry.source.id && s.connection === "disconnected",
    ),
  ).toBe(true);
  expect(
    afterOutage.state.some(
      (s: { source_id: string; freshness: string }) =>
        s.source_id !== telemetry.source.id && s.freshness === "good",
    ),
  ).toBe(true);
  await page.getByRole("tab", { name: "Documents", exact: true }).click();
  await page
    .getByText("Onesa illustrative pump maintenance — sections 1–5", {
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
    "Procedure evidence",
  );
  await page.getByRole("tab", { name: "Details", exact: true }).click();
  await page
    .getByLabel("Equipment", { exact: true })
    .selectOption({ label: "Demo pump 02 · ONESA-DEMO-PUMP-02-V2" });
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
  ).toBeVisible({ timeout: 15000 });
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
  ).toBeVisible({ timeout: 15000 });
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
    .getByText("Onesa illustrative pump maintenance — sections 1–5", {
      exact: true,
    })
    .click();
  await expect(page.getByRole("tabpanel", { name: "Documents" })).toContainText(
    "Section 2 — Bearing vibration inspection",
  );
});

test("detailed mechanical reference: explosion, hollow sections, internals, saved views and cleanup", async ({
  page,
  baseURL,
  browserName,
}, testInfo) => {
  test.setTimeout(180000);
  page.setDefaultTimeout(10000);
  await seeded(page, new URL(baseURL!).origin);
  await page
    .getByText("Section, subassembly and reveal controls", { exact: true })
    .click();
  const rendered = page.getByTestId("equipment-model-loaded");
  const evidenceDirectory = process.env.ONESA_TWIN_EVIDENCE_DIRECTORY;
  const profiles = [
    { width: 1440, height: 1000 },
    { width: 820, height: 1180 },
    { width: 390, height: 844 },
  ];
  const metrics: unknown[] = [];
  const settled = async () => {
    await expect(rendered).toHaveAttribute("data-inspection-settled", "true");
  };
  const capture = async (name: string, width: number) => {
    await settled();
    await rendered.scrollIntoViewIfNeeded();
    const actual = await rendered.evaluate((element) => {
      const canvas = element.querySelector("canvas")!;
      const gl = canvas.getContext("webgl2")!;
      const ext = gl.getExtension("WEBGL_debug_renderer_info");
      return {
        state: { ...(element as HTMLElement).dataset },
        canvas: [canvas.width, canvas.height],
        renderer: ext
          ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)
          : gl.getParameter(gl.RENDERER),
      };
    });
    const bounds = await page.locator("canvas").boundingBox();
    const frames: number[] = [],
      submitted: number[] = [];
    if (bounds) {
      const x = bounds.x + bounds.width * 0.5,
        y = bounds.y + bounds.height * 0.5;
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (let frame = 0; frame < 8; frame++) {
        const start = performance.now();
        await page.mouse.move(x + (frame + 1) * 3, y);
        const cpu = await rendered.evaluate(async (element) => {
          await new Promise(requestAnimationFrame);
          element.querySelector("canvas")!.getContext("webgl2")!.finish();
          return Number((element as HTMLElement).dataset.cpuSubmitMs || 0);
        });
        frames.push(performance.now() - start);
        submitted.push(cpu);
      }
      await page.mouse.up();
    }
    metrics.push({
      name,
      viewport: page.viewportSize(),
      browser: browserName,
      actual,
      orbit: { completedFrameWithAutomationMs: frames, cpuSubmitMs: submitted },
    });
    if (evidenceDirectory)
      fs.writeFileSync(
        path.join(
          evidenceDirectory,
          `premium-${browserName}-measurements.json`,
        ),
        JSON.stringify(metrics, null, 2),
      );
    if (evidenceDirectory)
      await rendered.screenshot({
        path: path.join(
          evidenceDirectory,
          `premium-${browserName}-${width}-${name}.png`,
        ),
      });
  };
  const catalog = await (
    await page.request.get("/api/v1/twins/catalog")
  ).json();
  expect(catalog.assets[0].definition.components).toHaveLength(68);
  const stable = Object.fromEntries(
    catalog.assets[0].definition.components.map(
      (c: { external_id: string; id: string }) => [c.external_id, c.id],
    ),
  );
  for (const viewport of profiles) {
    await page.setViewportSize(viewport);
    await page.getByRole("tab", { name: "Model", exact: true }).click();
    await page
      .getByRole("button", { name: "Restore all", exact: true })
      .click();
    await capture("assembled", viewport.width);
    await page.getByRole("button", { name: "Explode", exact: true }).click();
    await expect(rendered).toHaveAttribute("data-explode-fraction", "1.0000");
    await capture("exploded", viewport.width);
    await page
      .getByLabel("Explosion scope", { exact: true })
      .selectOption(stable.bearing as string);
    await page.getByRole("button", { name: "Bearing", exact: true }).click();
    await page
      .getByRole("button", { name: "Focus selected", exact: true })
      .click();
    await page.getByRole("button", { name: "Isolate", exact: true }).click();
    await capture("bearing-subassembly", viewport.width);
    // Pick genuinely moved geometry with a different component selected.
    await page.getByRole("button", { name: "Motor", exact: true }).click();
    await page.locator("canvas").scrollIntoViewIfNeeded();
    const box = await page.locator("canvas").boundingBox();
    let picked = false;
    for (const [x, y] of [
      [0.5, 0.22],
      [0.5, 0.28],
      [0.5, 0.32],
      [0.5, 0.75],
      [0.52, 0.28],
      [0.52, 0.73],
      [0.5, 0.5],
      [0.4, 0.4],
      [0.6, 0.4],
      [0.4, 0.6],
      [0.6, 0.6],
      [0.3, 0.5],
      [0.7, 0.5],
    ]) {
      if (!box || picked) break;
      await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
      picked =
        (await page
          .locator(
            "aside[aria-label='Equipment components'] button[aria-pressed='true']",
          )
          .filter({ hasText: /^Bearing ·/ })
          .count()) > 0;
    }
    if (!picked && evidenceDirectory)
      await rendered.screenshot({
        path: path.join(
          evidenceDirectory,
          `picking-failure-${browserName}-${viewport.width}.png`,
        ),
      });
    expect(
      picked,
      "Moved bearing geometry remains selectable by its stable identity",
    ).toBe(true);
    await page
      .getByRole("button", { name: "Restore all", exact: true })
      .click();
    await expect(rendered).toHaveAttribute("data-explode-fraction", "0.0000");
    await settled();
    expect(
      Number(await rendered.getAttribute("data-assembled-restoration-error")),
    ).toBe(0);
    await page.getByLabel("Section axis", { exact: true }).selectOption("z");
    await page.getByLabel("Section plane", { exact: true }).check();
    await expect(rendered).toHaveAttribute("data-section-active", "true");
    expect(
      Number(await rendered.getAttribute("data-section-caps")),
    ).toBeGreaterThan(0);
    await page.getByLabel("Reverse cut direction", { exact: true }).check();
    await capture("sectioned", viewport.width);
    await page.getByLabel("Ghost housings", { exact: true }).check();
    await capture("ghost-housings", viewport.width);
    await page
      .getByRole("button", { name: "Restore all", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Stator laminated core", exact: true })
      .click();
    await page.getByRole("button", { name: "Isolate", exact: true }).click();
    await page
      .getByRole("button", { name: "Focus selected", exact: true })
      .click();
    await capture("stator-closeup", viewport.width);
    if (viewport.width === 1440)
      for (const [part, name] of [
        ["Impeller", "impeller-closeup"],
        ["Copper winding phase A", "winding-closeup"],
        ["Rotor lamination stack", "rotor-closeup"],
      ]) {
        await page.getByRole("button", { name: part, exact: true }).click();
        await page
          .getByRole("button", { name: "Isolate", exact: true })
          .click();
        await page
          .getByRole("button", { name: "Focus selected", exact: true })
          .click();
        await capture(name, viewport.width);
      }
    await page
      .getByRole("button", { name: "Restore all", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Bearing · outer race", exact: true })
      .click();
    await page.getByRole("button", { name: "Isolate", exact: true }).click();
    await page
      .getByRole("button", { name: "Focus selected", exact: true })
      .click();
    await page.getByLabel("Section axis", { exact: true }).selectOption("x");
    await page.getByLabel("Section position", { exact: true }).fill("-45");
    await page.getByLabel("Reverse cut direction", { exact: true }).check();
    await page.getByLabel("Section plane", { exact: true }).check();
    await capture("bearing-cutface", viewport.width);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  await page.getByRole("button", { name: "Restore all", exact: true }).click();
  await page.getByLabel("Explosion percent", { exact: true }).fill("65");
  await page.getByLabel("Section axis", { exact: true }).selectOption("y");
  await page.getByLabel("Section plane", { exact: true }).check();
  await page.getByLabel("Ghost housings", { exact: true }).check();
  await settled();
  await page
    .getByRole("button", { name: "Save viewpoint", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Viewpoint 1", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(rendered).toBeVisible();
  await page.getByRole("button", { name: "Viewpoint 1", exact: true }).click();
  await expect(
    page.getByLabel("Explosion percent", { exact: true }),
  ).toHaveValue("65");
  await expect(
    page.getByLabel("Ghost housings", { exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel("Section axis", { exact: true })).toHaveValue(
    "y",
  );
  const after = await (await page.request.get("/api/v1/twins/catalog")).json();
  expect(
    Object.fromEntries(
      after.assets[0].definition.components.map(
        (c: { external_id: string; id: string }) => [c.external_id, c.id],
      ),
    ),
  ).toEqual(stable);
  // Actual route unmount/remount releases the old renderer and reloads owned bytes.
  for (let repeat = 0; repeat < 3; repeat++) {
    const previousCanvas = await page.locator("canvas").elementHandle();
    await page.getByRole("link", { name: "Knowledge", exact: true }).click();
    await expect(page.locator("canvas")).toHaveCount(0);
    await expect
      .poll(
        () =>
          previousCanvas!.evaluate((canvas: HTMLCanvasElement) =>
            canvas.getContext("webgl2")?.isContextLost(),
          ),
        { timeout: 10000 },
      )
      .toBe(true);
    await previousCanvas?.dispose();
    await page.goto("/industrial/twins");
    await expect(rendered).toBeVisible();
    expect(await page.locator("canvas").count()).toBe(1);
  }
  await testInfo.attach("premium-rendering-measurements", {
    body: JSON.stringify({
      hardware:
        "Recorded separately; mobile sizes are viewport emulation, not phone hardware",
      profiles: metrics,
    }),
    contentType: "application/json",
  });
  if (evidenceDirectory)
    fs.writeFileSync(
      path.join(evidenceDirectory, `premium-${browserName}-measurements.json`),
      JSON.stringify(metrics, null, 2),
    );
});
