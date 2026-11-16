import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { randomUUID } from "node:crypto";
import {
  createServer,
  request as httpRequest,
  type IncomingMessage,
  type ServerResponse,
} from "node:http";

const password = "nvidia-reference-synthetic-only-123!";
const accounts = new WeakMap<Page, string>();
const externalRequests = new WeakMap<Page, string[]>();
const allowedOrigins = new WeakMap<Page, Set<string>>();

async function headers(page: Page, origin: string) {
  return {
    Origin: origin,
    "X-CSRF-Token":
      (await page.context().cookies(origin)).find(
        (cookie) => cookie.name === "onesa_csrf",
      )?.value || "",
  };
}

test.beforeEach(async ({ page, baseURL }) => {
  const origin = new URL(baseURL!).origin;
  if (!["127.0.0.1", "localhost", "[::1]"].includes(new URL(origin).hostname))
    throw new Error(
      "Reference browser mutations require isolated loopback fixtures",
    );
  const requests: string[] = [];
  const origins = new Set([origin]);
  externalRequests.set(page, requests);
  allowedOrigins.set(page, origins);
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (origins.has(url.origin) || ["blob:", "data:"].includes(url.protocol))
      return route.continue();
    requests.push(url.origin);
    return route.abort("blockedbyclient");
  });
  const email = `nvidia-${randomUUID()}@example.com`;
  const response = await page.request.post("/api/v1/auth/register", {
    headers: { Origin: origin },
    data: { email, password, display_name: "Synthetic reference reviewer" },
  });
  expect(response.status()).toBe(201);
  accounts.set(page, email);
});

test.afterEach(async ({ page, baseURL }) => {
  expect(externalRequests.get(page)).toEqual([]);
  const email = accounts.get(page);
  if (!email) return;
  const origin = new URL(baseURL!).origin;
  const login = await page.request.post("/api/v1/auth/login", {
    headers: { Origin: origin },
    data: { email, password },
  });
  expect(login.status()).toBe(200);
  const removed = await page.request.post("/api/v1/account/delete", {
    headers: await headers(page, origin),
    data: { current_password: password, confirmation: "DELETE MY ACCOUNT" },
  });
  expect(removed.status()).toBe(204);
});

async function ready(page: Page) {
  await expect(page.getByTestId("reference-model-loaded")).toBeVisible({
    timeout: 30000,
  });
  await expect
    .poll(
      async () =>
        Number(
          await page
            .getByTestId("reference-model-loaded")
            .getAttribute("data-draw-calls"),
        ),
      { timeout: 30000 },
    )
    .toBeGreaterThan(0);
  expect(
    await page
      .getByTestId("nvidia-reference-preview")
      .locator("canvas")
      .evaluate((canvas) => canvas.clientHeight),
  ).toBeGreaterThanOrEqual(300);
}

// Observe cookies and redirects on the wire, after the browser network stack.
// Playwright routes run before Cookie is attached and cannot fulfill 3xx in WebKit.
async function referenceProxy(
  page: Page,
  baseURL: string,
  intercept: (request: IncomingMessage, response: ServerResponse) => boolean,
) {
  const upstream = new URL(baseURL);
  if (
    upstream.protocol !== "http:" ||
    !["127.0.0.1", "localhost", "[::1]"].includes(upstream.hostname) ||
    upstream.username ||
    upstream.password ||
    upstream.pathname !== "/" ||
    upstream.search ||
    upstream.hash
  )
    throw new Error("Reference transport fixtures require a loopback HTTP origin");
  const violations: string[] = [];
  const pending = new Set<ReturnType<typeof httpRequest>>();
  const server = createServer((request, response) => {
    if (
      !["GET", "HEAD"].includes(request.method || "") ||
      !request.url?.startsWith("/") ||
      request.url.startsWith("//")
    ) {
      response.writeHead(400).end();
      return;
    }
    if (/^\/models\/nvidia\/.*\.glb$/.test(request.url)) {
      if (request.method !== "GET") violations.push("Reference method is not GET");
      if (request.headers.authorization !== undefined)
        violations.push("Reference request contains an Authorization header");
      if (violations.length) {
        response.writeHead(400).end();
        return;
      }
    }
    if (intercept(request, response)) return;
    const forwarded = httpRequest(
      {
        hostname: upstream.hostname.replace(/^\[|\]$/g, ""),
        port: upstream.port,
        path: request.url,
        method: request.method,
        headers: {
          ...request.headers,
          host: upstream.host,
          connection: "close",
        },
      },
      (received) => {
        response.writeHead(received.statusCode || 502, {
          ...received.headers,
          "cache-control": "no-store",
        });
        received.pipe(response);
      },
    );
    pending.add(forwarded);
    forwarded.once("close", () => pending.delete(forwarded));
    forwarded.on("error", () => {
      if (!response.headersSent) response.writeHead(502);
      response.end();
    });
    forwarded.setTimeout(10000, () => forwarded.destroy());
    forwarded.end();
  });
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, upstream.hostname.replace(/^\[|\]$/g, ""), () => {
      server.removeListener("error", reject);
      resolve();
    });
  });
  const address = server.address();
  if (!address || typeof address === "string")
    throw new Error("Reference transport fixture did not bind a TCP port");
  const origin = `${upstream.protocol}//${upstream.hostname}:${address.port}`;
  allowedOrigins.get(page)!.add(origin);
  return {
    origin,
    violations,
    async close() {
      allowedOrigins.get(page)!.delete(origin);
      for (const request of pending) request.destroy();
      await new Promise<void>((resolve, reject) => {
        server.close((error) => (error ? reject(error) : resolve()));
        server.closeAllConnections();
      });
    },
  };
}

test("references load automatically, remain local and retain source attribution", async ({
  page,
}, testInfo) => {
  test.setTimeout(90000);
  await page.goto("/industrial/twins");
  await expect(
    page.getByRole("heading", { name: "NVIDIA reference models" }),
  ).toBeVisible();
  for (const name of ["Transfer conveyor", "Mobile cart", "Warehouse rack"]) {
    await page.getByRole("button", { name, exact: true }).click();
    await ready(page);
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "NVIDIA source", exact: true }),
    ).toHaveAttribute("href", /4763fbfaa4f8e97658e68b57d01b4c86659e08b5/);
    expect(
      Number(
        await page
          .getByTestId("reference-model-loaded")
          .getAttribute("data-triangles"),
      ),
    ).toBeLessThanOrEqual(30000);
  }
  await expect(
    page.getByRole("button", { name: "Add to my workspace" }),
  ).toBeEnabled();
  await page
    .getByTestId("nvidia-reference-preview")
    .screenshot({ path: testInfo.outputPath("nvidia-reference-preview.png") });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Fit reference view" }).click();
  await ready(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page
    .getByTestId("nvidia-reference-preview")
    .screenshot({ path: testInfo.outputPath("nvidia-reference-mobile.png") });
});

test("private import survives reload and carries no live observations", async ({
  page,
  baseURL,
}) => {
  await page.goto("/industrial/twins");
  await page.getByRole("button", { name: "Mobile cart", exact: true }).click();
  await page.getByRole("button", { name: "Add to my workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "NVIDIA Mobile cart", exact: true }),
  ).toBeVisible();
  await expect(page.getByTestId("equipment-model-loaded")).toBeVisible({
    timeout: 30000,
  });
  const response = await page.request.get("/api/v1/twins/catalog");
  const assets = (await response.json()).assets;
  expect(assets).toHaveLength(1);
  const detail = await (
    await page.request.get(`/api/v1/twins/assets/${assets[0].id}`)
  ).json();
  expect(detail.state).toEqual([]);
  expect(detail.sources).toEqual([]);
  expect(detail.asset.definition.reference.license).toBe("CC-BY-4.0");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "NVIDIA Mobile cart", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "NVIDIA reference library", exact: true })
    .click();
  await page.getByRole("button", { name: "Mobile cart", exact: true }).click();
  await page.getByRole("button", { name: "Add to my workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "NVIDIA Mobile cart", exact: true }),
  ).toBeVisible();
  expect(
    (
      await (
        await page.request.get("/api/v1/twins/catalog", {
          headers: await headers(page, new URL(baseURL!).origin),
        })
      ).json()
    ).assets,
  ).toHaveLength(1);
});

test("lost import response retries without duplicating the owned reference", async ({
  page,
}) => {
  let accepted = "";
  await page.route("**/api/v1/twins/references/*/import", async (route) => {
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    accepted = (await response.json()).asset.id;
    await route.abort("failed");
  });
  await page.goto("/industrial/twins");
  await page.getByRole("button", { name: "Add to my workspace" }).click();
  await expect(page.locator(".error[role=alert]")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Add to my workspace" }),
  ).toBeEnabled();
  expect(accepted).not.toBe("");
  await page.unroute("**/api/v1/twins/references/*/import");
  await page.getByRole("button", { name: "Add to my workspace" }).click();
  await expect(
    page.getByRole("heading", {
      name: "NVIDIA Transfer conveyor",
      exact: true,
    }),
  ).toBeVisible();
  const assets = (
    await (await page.request.get("/api/v1/twins/catalog")).json()
  ).assets;
  expect(assets).toHaveLength(1);
  expect(assets[0].id).toBe(accepted);
});

for (const status of [401, 503])
  test(`reference download ${status} preserves the session and recovers on retry`, async ({
    page,
  }) => {
    let refuse = true;
    await page.route("**/models/nvidia/**/*.glb", (route) =>
      refuse
        ? route.fulfill({ status, body: "unavailable" })
        : route.continue(),
    );
    await page.goto("/industrial/twins");
    await expect(
      page.getByAltText(
        "Transfer conveyor, rendered from the same NVIDIA reference model",
      ),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Add to my workspace" }),
    ).toBeEnabled();
    expect((await page.request.get("/api/v1/twins/catalog")).status()).toBe(
      200,
    );
    refuse = false;
    await page.getByRole("button", { name: "Reload 3D preview" }).click();
    await ready(page);
  });

test("protected preview cookies permit same-origin reference rendering", async ({
  page,
  baseURL,
}) => {
  const cookie = "onesa_reference_preview=synthetic-preview-session";
  const accepted = new Set<string>();
  let refused = 0;
  const proxy = await referenceProxy(page, baseURL!, (request, response) => {
    if (!/^\/models\/nvidia\/.*\.glb$/.test(request.url!)) return false;
    if (
      !(request.headers.cookie || "")
        .split(";")
        .some((value) => value.trim() === cookie)
    ) {
      refused++;
      response
        .writeHead(401, { "cache-control": "no-store" })
        .end("Preview authentication required");
      return true;
    }
    accepted.add(request.url!);
    return false;
  });
  try {
    await page.goto(`${proxy.origin}/industrial/twins`);
    await expect(
      page.getByAltText(
        "Transfer conveyor, rendered from the same NVIDIA reference model",
      ),
    ).toBeVisible();
    expect(refused).toBeGreaterThan(0);
    expect(accepted.size).toBe(0);
    const before = refused;
    await page.context().addCookies([
      {
        name: "onesa_reference_preview",
        value: "synthetic-preview-session",
        url: proxy.origin,
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    expect(await page.evaluate(() => document.cookie)).not.toContain(
      "onesa_reference_preview",
    );
    await page.getByRole("button", { name: "Reload 3D preview" }).click();
    await ready(page);
    for (const name of ["Mobile cart", "Warehouse rack"]) {
      await page.getByRole("button", { name, exact: true }).click();
      await ready(page);
    }
    expect(refused).toBe(before);
    expect(accepted.size).toBe(3);
    expect((await page.request.get("/api/v1/twins/catalog")).status()).toBe(200);
  } finally {
    await proxy.close();
    expect(proxy.violations).toEqual([]);
  }
});

test("reference redirects are refused before a second request and can recover", async ({
  page,
  baseURL,
}) => {
  const targetPath = "/reference-redirect-fixture.glb";
  let wireRequests = 0;
  let redirects = 0;
  let redirectedRequests = 0;
  let redirect = true;
  const proxy = await referenceProxy(page, baseURL!, (request, response) => {
    if (request.url === targetPath) {
      wireRequests++;
      response.writeHead(410).end();
      return true;
    }
    if (redirect && /^\/models\/nvidia\/.*\.glb$/.test(request.url!)) {
      redirects++;
      response
        .writeHead(302, { Location: targetPath, "cache-control": "no-store" })
        .end();
      return true;
    }
    return false;
  });
  const target = new URL(targetPath, proxy.origin).href;
  page.on("request", (request) => {
    if (request.url() === target) redirectedRequests++;
  });
  try {
    await page.goto(`${proxy.origin}/industrial/twins`);
    await expect(
      page.getByAltText(
        "Transfer conveyor, rendered from the same NVIDIA reference model",
      ),
    ).toBeVisible();
    expect(redirects).toBeGreaterThan(0);
    expect(wireRequests).toBe(0);
    expect(redirectedRequests).toBe(0);
    expect((await page.request.get("/api/v1/twins/catalog")).status()).toBe(200);
    redirect = false;
    await page.getByRole("button", { name: "Reload 3D preview" }).click();
    await ready(page);
    expect(wireRequests).toBe(0);
    expect(redirectedRequests).toBe(0);
  } finally {
    await proxy.close();
    expect(proxy.violations).toEqual([]);
  }
});

test("mobile fallback keeps explanation, keyboard actions and import reachable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (
      this: HTMLCanvasElement,
      ...args: Parameters<typeof original>
    ) {
      if (
        String(args[0]).startsWith("webgl") ||
        args[0] === "experimental-webgl"
      )
        return null;
      return original.apply(this, args);
    } as typeof original;
  });
  await page.goto("/industrial/twins");
  const fallback = page.getByAltText(
    "Transfer conveyor, rendered from the same NVIDIA reference model",
  );
  await expect(fallback).toBeVisible({ timeout: 30000 });
  await expect(
    page.getByText(
      "3D is unavailable. This image shows the same model; its details and import action remain available.",
    ),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const selection = page.getByRole("button", {
    name: "Mobile cart",
    exact: true,
  });
  await selection.focus();
  await page.keyboard.press("Enter");
  await expect(selection).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByAltText(
      "Mobile cart, rendered from the same NVIDIA reference model",
    ),
  ).toBeVisible();
  const violations = (
    await new AxeBuilder({ page })
      .include('section[aria-labelledby="reference-library-title"]')
      .analyze()
  ).violations;
  expect(violations).toEqual([]);
});

test("theme changes preserve selected model and do not download it again", async ({
  page,
}) => {
  let loads = 0;
  page.on("request", (request) => {
    if (
      request.url().includes("/models/nvidia/") &&
      request.url().endsWith(".glb")
    )
      loads++;
  });
  await page.goto("/industrial/twins");
  await page
    .getByRole("button", { name: "Warehouse rack", exact: true })
    .click();
  await ready(page);
  const before = loads;
  for (const colorScheme of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
    await expect(
      page.getByRole("button", { name: "Warehouse rack", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Fit reference view" }).click();
    await ready(page);
    expect(loads).toBe(before);
    const violations = (
      await new AxeBuilder({ page })
        .include('section[aria-labelledby="reference-library-title"]')
        .analyze()
    ).violations;
    expect(violations, `${colorScheme} reference library contrast`).toEqual([]);
  }
});

test("catalog failure can recover while existing equipment controls stay available", async ({
  page,
}) => {
  let refuse = true;
  await page.route("**/api/v1/twins/references", (route) =>
    refuse
      ? route.fulfill({
          status: 503,
          contentType: "application/json",
          body: '{"error":{"code":"twin_reference_unavailable","message":"Unavailable"}}',
        })
      : route.continue(),
  );
  await page.goto("/industrial/twins");
  await expect(
    page.getByText(
      "The reference library is unavailable. Your equipment remains available.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Load isolated pump demonstration" }),
  ).toBeEnabled();
  refuse = false;
  await page.getByRole("button", { name: "Retry reference library" }).click();
  await ready(page);
});

test("graphics context loss retains image fallback and offers a new preview", async ({
  page,
}) => {
  await page.goto("/industrial/twins");
  await ready(page);
  await page
    .getByTestId("nvidia-reference-preview")
    .locator("canvas")
    .evaluate((canvas) =>
      canvas.dispatchEvent(new Event("webglcontextlost", { cancelable: true })),
    );
  await expect(
    page.getByAltText(
      "Transfer conveyor, rendered from the same NVIDIA reference model",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reload 3D preview" }).click();
  await ready(page);
});

test("changing a reference and leaving the library release old graphics contexts", async ({
  page,
}) => {
  await page.goto("/industrial/twins");
  await ready(page);
  const previous = await page
    .getByTestId("nvidia-reference-preview")
    .locator("canvas")
    .elementHandle();
  await page.getByRole("button", { name: "Mobile cart", exact: true }).click();
  await ready(page);
  await expect
    .poll(() =>
      previous!.evaluate((canvas: HTMLCanvasElement) =>
        canvas.getContext("webgl2")?.isContextLost(),
      ),
    )
    .toBe(true);
  await previous?.dispose();
  const current = await page
    .getByTestId("nvidia-reference-preview")
    .locator("canvas")
    .elementHandle();
  await page.getByRole("link", { name: "Knowledge", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect
    .poll(() =>
      current!.evaluate((canvas: HTMLCanvasElement) =>
        canvas.getContext("webgl2")?.isContextLost(),
      ),
    )
    .toBe(true);
  await current?.dispose();
});
