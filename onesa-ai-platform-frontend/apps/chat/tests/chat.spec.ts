import { test, expect } from "@playwright/test";
test("register, stream, reopen, rename, delete, sign in", async ({ page }) => {
  const email = `browser-${Date.now()}@example.com`;
  await page.goto("/");
  await page
    .getByRole("button", { name: "New to Onesa? Create an account" })
    .click();
  await page.getByLabel("Display name").fill("Browser Tester");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-password-123!");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "＋ New conversation" }),
  ).toBeVisible();
  await page.getByLabel("Message Onesa AI").fill("Hello from browser");
  await page.getByLabel("Send message").click();
  await expect(
    page.getByText("[Mock response — no AI inference] Hello from browser"),
  ).toBeVisible();
  await page.screenshot({
    path: "../../../data/screenshots/chat-desktop.png",
    fullPage: true,
  });
  await page.reload();
  await page
    .getByRole("button", { name: "Hello from browser", exact: true })
    .click();
  await expect(
    page.getByText("[Mock response — no AI inference] Hello from browser"),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept("Saved chat"));
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Saved chat", exact: true }),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Saved chat", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-password-123!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "＋ New conversation" }),
  ).toBeVisible();
});

test("documents, source-grounded chat, bounded tools and saved travel", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "New to Onesa? Create an account" })
    .click();
  await page.getByLabel("Display name").fill("Workspace Tester");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`workspace-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("workspace-password-123!");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "＋ New conversation" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Knowledge", exact: true }).click();
  await page.getByLabel("Document (.txt or .pdf, up to 5 MiB)").setInputFiles({
    name: "zimbabwe.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Harare is the capital of Zimbabwe."),
  });
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  await expect(page.getByText("zimbabwe.txt", { exact: true })).toBeVisible();
  await page.getByRole("button", {name:"Preview extracted text"}).click();
  await expect(page.getByRole("heading", {name:"Preview: zimbabwe.txt"})).toBeVisible();
  await expect(page.getByText("Harare is the capital of Zimbabwe.", {exact:true})).toBeVisible();
  await page.getByRole("button", {name:"Close preview"}).click();
  await page.getByRole("button", {name:"Rebuild search index"}).click();
  await expect(page.getByRole("status")).toContainText("Document search index rebuilt");
  await page.getByRole("link", { name: "Ask about this document →" }).click();
  await page.getByLabel("Message Onesa AI").fill("What is Harare?");
  await page.getByLabel("Send message").click();
  await expect(page.getByText(/Retrieved excerpts/)).toBeVisible();
  await expect(page.locator(".sources")).toContainText("zimbabwe.txt");
  await page.getByRole("link", { name: "Agents", exact: true }).click();
  await page.getByLabel("Text to analyze").fill("Count these three words");
  await page.getByLabel("Allow the text-statistics tool for this run").check();
  await page.getByRole("button", { name: "Run tool", exact: true }).click();
  await expect(page.getByText("completed", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Travel", exact: true }).click();
  await page.getByLabel("Destination", { exact: true }).fill("Victoria Falls");
  await page.getByRole("button", { name: "Create plan", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Victoria Falls · revision 1" }),
  ).toBeVisible();
  await expect(page.getByText(/Current prices/)).toBeVisible();
  await page.getByLabel("Days", { exact: true }).fill("2");
  await page.getByRole("button", { name: "Revise plan", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Victoria Falls · revision 2" }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByRole("button", { name: "Victoria Falls · 2 days", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Victoria Falls · revision 2" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../../../data/screenshots/travel-desktop.png",
    fullPage: true,
  });
});

test("mobile keyboard chat", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page
    .getByRole("button", { name: "New to Onesa? Create an account" })
    .click();
  await page.getByLabel("Display name").fill("Mobile Tester");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`mobile-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("mobile-password-123!");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.getByLabel("Message Onesa AI").fill("Hello mobile");
  await page.getByLabel("Message Onesa AI").press("Enter");
  await expect(
    page.getByText("[Mock response — no AI inference] Hello mobile"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Toggle conversations" }).click();
  await expect(
    page.getByRole("button", { name: "Hello mobile", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Hello mobile", exact: true }).click();
  await expect(
    page.getByText("[Mock response — no AI inference] Hello mobile"),
  ).toBeVisible();
  await expect(page.locator(".sidebar.open")).toHaveCount(0);
  await page.getByRole("button", { name: "Toggle conversations" }).click();
  await page.keyboard.press("Escape");
  await expect(page.locator(".sidebar.open")).toHaveCount(0);
  await page.screenshot({
    path: "../../../data/screenshots/chat-mobile.png",
    fullPage: true,
  });
});

test("interface language preference persists independently of model support", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Interface language").selectOption("de");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(
    page.getByRole("heading", { name: "Willkommen zurück" }),
  ).toBeVisible();
  await expect(page.getByLabel("Passwort", { exact: true })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Anmelden", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Sprache der Oberfläche").selectOption("en");
  await expect(
    page.getByRole("heading", { name: "Welcome back" }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
});

test("same-origin API redirects and private metrics boundaries", async ({ request, baseURL }) => {
  const redirect = await request.get("/api/v1/auth/me/", { maxRedirects: 0 });
  expect([307, 308]).toContain(redirect.status());
  const location = new URL(redirect.headers().location, baseURL);
  expect(location.origin).toBe(new URL(baseURL!).origin);
  expect(location.pathname).toBe("/api/v1/auth/me");
  expect((await request.get("/metrics")).status()).toBe(404);
  expect((await request.get("/api/metrics")).status()).toBe(404);
});
