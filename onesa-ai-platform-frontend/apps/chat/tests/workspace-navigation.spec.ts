import { test, expect, type Page } from "@playwright/test";

// Production UI with explicit loopback fixtures; no backend or model acceptance.
test.beforeEach(async ({ page, baseURL }) => {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL!).hostname)) {
    throw new Error("Loopback UI fixtures only");
  }
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    if (path === "/api/v1/auth/me") {
      body = { id: "navigation-fixture", display_name: "Synthetic navigation tester" };
    } else if (path === "/api/v1/documentation/access") {
      body = { engineering: false };
    } else if (path === "/api/v1/models") {
      body = { items: [{ backend: "mock", model_identifier: "navigation-fixture", real_inference: false }] };
    } else if (path === "/api/v1/conversations") {
      body = { items: [{ id: "saved-plan", title: "Saved project plan" }], next_cursor: null };
    } else if (path === "/api/v1/conversations/saved-plan") {
      body = { messages: [{ id: "saved-answer", role: "assistant", content: {
        text: "## Saved plan\n\n" + Array.from({ length: 32 }, (_, index) =>
          `${index + 1}. Synthetic planning detail to exercise a long saved conversation.`).join("\n\n"),
      } }] };
    } else if (path === "/api/v1/knowledge/documents") {
      body = { items: [], next_cursor: null };
    } else {
      await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
      return;
    }
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
});

async function expectInViewport(page: Page, selector: string) {
  const bounds = await page.locator(selector).boundingBox();
  expect(bounds).not.toBeNull();
  expect(bounds!.y).toBeGreaterThanOrEqual(0);
  expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(page.viewportSize()!.height + 1);
}

for (const mode of ["light", "dark"] as const) {
  test(`saved chat keeps navigation and composer visible in ${mode} mode`, async ({ page }, info) => {
    test.setTimeout(60000);
    await page.emulateMedia({ colorScheme: mode, reducedMotion: "reduce" });
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 680 }]) {
      await page.setViewportSize(viewport);
      await page.goto("/");
      const draft = page.getByLabel("Message Onesa AI");
      await expect(draft).toBeEnabled();
      await draft.fill("Keep this unsent question");
      if (viewport.width <= 700) await page.getByRole("button", { name: "Toggle conversations" }).click();
      await page.getByRole("button", { name: "Saved project plan", exact: true }).click();
      await expect(page.locator(".message.assistant").getByRole("heading", { name: "Saved plan" })).toBeVisible();
      await expect(page.locator(".message.assistant li")).toHaveCount(32);
      await expect(draft).toHaveValue("Keep this unsent question");
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
      expect(await page.locator(".messages").evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true);
      await expectInViewport(page, ".topbar");
      await expectInViewport(page, ".input-wrap");
      if (viewport.width <= 700) await expectInViewport(page, '.topbar button[aria-label="Toggle conversations"]');
      const caption = await page.locator(".composer .caption").boundingBox();
      const footer = await page.locator(".company-footer").boundingBox();
      expect(caption!.y + caption!.height).toBeLessThanOrEqual(footer!.y + 1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.locator(".messages").evaluate(element => { element.scrollTop = 0; });
      await expect.poll(() => page.locator(".messages").evaluate(element => element.scrollTop)).toBe(0);
      await page.emulateMedia({ colorScheme: mode === "light" ? "dark" : "light" });
      await expect(draft).toHaveValue("Keep this unsent question");
      expect(await page.locator(".messages").evaluate(element => element.scrollTop)).toBe(0);
      await page.emulateMedia({ colorScheme: mode });
      await page.screenshot({ path: info.outputPath(`chat-${mode}-${viewport.width}.png`), fullPage: true });
    }
  });
}

test("mobile workspace options preserve the task and return keyboard focus", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Your knowledge", exact: true })).toBeVisible();
  const query = page.getByLabel("Search your documents", { exact: true });
  await query.fill("Keep this search draft");
  const options = page.getByRole("button", { name: "Workspace options", exact: true });
  await expect(options).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("link", { name: "Account settings", exact: true })).toBeHidden();
  await options.click();
  await expect(options).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("link", { name: "Account settings", exact: true })).toBeVisible();
  await page.getByLabel("Interface language").selectOption("de");
  await expect(query).toHaveValue("Keep this search draft");
  await page.getByRole("link", { name: "Account settings", exact: true }).focus();
  await page.keyboard.press("Escape");
  const translatedOptions = page.getByRole("button", { name: "Arbeitsbereich-Menü", exact: true });
  await expect(translatedOptions).toBeFocused();
  await expect(translatedOptions).toHaveAttribute("aria-expanded", "false");
  const navigation = page.getByRole("navigation", { name: "AI workspace", exact: true });
  const chat = navigation.getByRole("link", { name: "Chat", exact: true });
  await expect(chat).toBeVisible();
  expect((await chat.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await chat.click();
  await expect(page.getByLabel("Message Onesa AI")).toBeEnabled();
});

for (const route of ["/", "/knowledge"]) {
  for (const width of [390, 1440]) {
    test(`account settings loads on selection from ${route} at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      await page.route("**/api/v1/auth/me", route => route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ id: "navigation-fixture", display_name: "Synthetic navigation tester", email: "navigation@example.com" }),
      }));
      await page.route("**/api/v1/auth/sessions", route => route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, limit: 20 }),
      }));
      const errors: string[] = [];
      const settingsBeforeSelection: string[] = [];
      const primaryPrefetches: string[] = [];
      let selected = false;
      page.on("pageerror", error => errors.push(error.message));
      page.on("request", request => {
        const url = new URL(request.url());
        if (!selected && url.pathname === "/settings" && url.searchParams.has("_rsc")) {
          settingsBeforeSelection.push(url.pathname);
        }
        if (url.pathname === "/agents" && request.headers()["next-router-prefetch"] === "1") {
          primaryPrefetches.push(url.pathname);
        }
      });

      await page.goto(route);
      if (route === "/") {
        await expect(page.getByLabel("Message Onesa AI")).toBeEnabled();
        if (width === 390) await page.getByRole("button", { name: "Toggle conversations" }).click();
      } else {
        await expect(page.getByRole("heading", { name: "Your knowledge", exact: true })).toBeVisible();
        if (width === 390) await page.getByRole("button", { name: "Workspace options", exact: true }).click();
      }
      const settings = page.getByRole("link", { name: "Account settings", exact: true });
      await expect(settings).toBeVisible();
      await settings.hover();
      // A real primary-route prefetch keeps this check meaningful in a production build.
      await expect.poll(() => primaryPrefetches.length).toBeGreaterThan(0);
      expect(settingsBeforeSelection).toEqual([]);
      await page.evaluate(() => { document.documentElement.dataset.navigationFixture = "preserved"; });
      selected = true;
      await settings.click();
      await expect(page).toHaveURL(/\/settings$/);
      await expect(page.getByRole("heading", { name: "Account settings", exact: true })).toBeVisible();
      await expect(page.getByText("Signed in as navigation@example.com", { exact: true })).toBeVisible();
      await expect(page.getByLabel("Display name", { exact: true })).toHaveValue("Synthetic navigation tester");
      expect(await page.evaluate(() => document.documentElement.dataset.navigationFixture)).toBe("preserved");
      expect(errors).toEqual([]);
    });
  }
}
