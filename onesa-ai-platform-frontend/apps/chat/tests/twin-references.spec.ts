import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { randomUUID } from "node:crypto";

const password = "nvidia-reference-synthetic-only-123!";
const accounts = new WeakMap<Page, string>();
const externalRequests = new WeakMap<Page, string[]>();

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
  externalRequests.set(page, requests);
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.origin === origin || ["blob:", "data:"].includes(url.protocol))
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
  const origin = new URL(baseURL!).origin;
  const cookie = "onesa_reference_preview=synthetic-preview-session";
  await page.context().addCookies([
    {
      name: "onesa_reference_preview",
      value: "synthetic-preview-session",
      url: origin,
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  let accepted = 0;
  let refused = 0;
  await page.route("**/models/nvidia/**/*.glb", async (route) => {
    const headers = await route.request().allHeaders();
    if (!(headers.cookie || "").split(";").some((value) => value.trim() === cookie)) {
      refused++;
      return route.fulfill({ status: 401, body: "Preview authentication required" });
    }
    accepted++;
    return route.continue();
  });
  await page.goto("/industrial/twins");
  await expect.poll(() => accepted + refused).toBeGreaterThan(0);
  expect(refused).toBe(0);
  await ready(page);
  expect(accepted).toBeGreaterThan(0);
});

test("reference redirects are refused before a second request and can recover", async ({
  page,
  baseURL,
}) => {
  const target = new URL("/reference-redirect-fixture.glb", baseURL!).href;
  let redirectedRequests = 0;
  let redirect = true;
  page.on("request", (request) => {
    if (request.url() === target) redirectedRequests++;
  });
  await page.route("**/models/nvidia/**/*.glb", (route) =>
    redirect
      ? route.fulfill({ status: 302, headers: { Location: target }, body: "" })
      : route.continue(),
  );
  await page.goto("/industrial/twins");
  await expect(
    page.getByAltText(
      "Transfer conveyor, rendered from the same NVIDIA reference model",
    ),
  ).toBeVisible();
  expect(redirectedRequests).toBe(0);
  expect((await page.request.get("/api/v1/twins/catalog")).status()).toBe(200);
  redirect = false;
  await page.getByRole("button", { name: "Reload 3D preview" }).click();
  await ready(page);
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
  await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
  await expect(
    page.getByRole("button", { name: "Warehouse rack", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Fit reference view" }).click();
  await ready(page);
  await page.emulateMedia({ colorScheme: "light" });
  await ready(page);
  expect(loads).toBe(before);
  const violations = (
    await new AxeBuilder({ page })
      .include('section[aria-labelledby="reference-library-title"]')
      .analyze()
  ).violations;
  expect(violations).toEqual([]);
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
