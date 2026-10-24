import { test, expect, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const reply = (route: Route, body: unknown, status = 200) =>
  route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
const trip = (id: string, destination: string, revision = 1) => ({
  id,
  destination,
  duration: 3,
  budget: 500,
  currency: "USD",
  preferences: "Museums",
  revision,
  notice: "Synthetic test itinerary",
  itinerary: { backend: "mock", days: [], assumptions: [] },
});
test.beforeEach(async ({ page, baseURL }) => {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL!).hostname))
    throw new Error(
      "Synthetic transport fixtures require loopback; never production.",
    );
  await page.route("**/api/**", (route) =>
    reply(route, { error: { message: "Unconfigured synthetic request" } }, 503),
  );
  await page.route("**/api/v1/auth/me", (route) =>
    reply(route, { id: "synthetic-user-a" }),
  );
  await page.route("**/api/v1/auth/login", (route) =>
    reply(route, { id: "synthetic-user-a" }),
  );
  await page.route("**/api/v1/documentation/access", (route) =>
    reply(route, { engineering: false }),
  );
  await page.route("**/api/v1/travel/trips{,?*}", (route) =>
    reply(route, { items: [trip("a", "Lisbon"), trip("b", "Berlin")] }),
  );
  await page.route("**/api/v1/knowledge/documents{,?*}", (route) =>
    reply(route, { items: [] }),
  );
});
for (const path of ["/travel", "/knowledge"]) {
  test(`${path}: authenticate before protected work and retain task`, async ({
    page,
  }) => {
    let authenticated = false,
      protectedReads = 0;
    await page.route("**/api/v1/auth/me", (route) =>
      reply(route, { error: { message: "Sign in" } }, 401),
    );
    await page.route("**/api/v1/auth/login", (route) => {
      authenticated = true;
      return reply(route, { id: "synthetic-user-a" });
    });
    await page.route(
      path === "/travel"
        ? "**/api/v1/travel/trips{,?*}"
        : "**/api/v1/knowledge/documents{,?*}",
      (route) => {
        expect(authenticated).toBe(true);
        protectedReads++;
        return reply(route, { items: [] });
      },
    );
    await page.goto(path);
    await expect(
      page.getByRole("button", { name: "Sign in and continue" }),
    ).toBeVisible();
    await expect(
      page.getByLabel(
        path === "/travel"
          ? "Destination"
          : "Document (.txt or .pdf, up to 5 MiB)",
      ),
    ).toHaveCount(0);
    expect(protectedReads).toBe(0);
    await page
      .getByLabel("Email", { exact: true })
      .fill("synthetic@example.test");
    await page
      .getByLabel("Password", { exact: true })
      .fill("Synthetic-only-password");
    await page.getByRole("button", { name: "Sign in and continue" }).click();
    await expect(
      page.getByLabel(
        path === "/travel"
          ? "Destination"
          : "Document (.txt or .pdf, up to 5 MiB)",
      ),
    ).toBeVisible();
    expect(new URL(page.url()).pathname).toBe(path);
    await expect.poll(() => protectedReads).toBeGreaterThan(0);
  });
}
for (const colorScheme of ["light", "dark"] as const) {
  test(`${colorScheme}: trip, new and app navigation offer stay/discard`, async ({
    page,
  }, info) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ colorScheme, reducedMotion: "reduce" });
    await page.goto("/travel");
    await page
      .getByLabel("Destination", { exact: true })
      .fill("Unsent private destination");
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("button", { name: "Berlin · 3 days" }).click();
    await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
      "Unsent private destination",
    );
    page.once("dialog", (dialog) => dialog.dismiss());
    await page.getByRole("button", { name: "New trip" }).click();
    await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
      "Unsent private destination",
    );
    page.once("dialog", (dialog) => dialog.dismiss());
    await page
      .getByRole("navigation", { name: "AI workspace" })
      .getByRole("link", { name: "Knowledge", exact: true })
      .click();
    await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
      "Unsent private destination",
    );
    expect(
      await page.evaluate(() =>
        JSON.stringify([localStorage, sessionStorage, history.state]).includes(
          "Unsent private destination",
        ),
      ),
    ).toBe(false);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({
      path: info.outputPath(`travel-draft-${colorScheme}.png`),
      fullPage: true,
    });
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Berlin · 3 days" }).click();
    await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
      "Berlin",
    );
  });
}
test("Back can stay with draft; discard permits Back and Forward", async ({
  page,
}) => {
  await page.goto("/knowledge");
  await page
    .getByRole("navigation", { name: "AI workspace" })
    .getByRole("link", { name: "Travel", exact: true })
    .click();
  await page.getByLabel("Destination", { exact: true }).fill("Keep on Back");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.evaluate(() => history.back());
  await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
    "Keep on Back",
  );
  await expect(page).toHaveURL(/\/travel$/);
  page.once("dialog", (dialog) => dialog.accept());
  await page.evaluate(() => history.back());
  await expect(
    page.getByLabel("Document (.txt or .pdf, up to 5 MiB)"),
  ).toBeVisible();
  await page.evaluate(() => history.forward());
  await expect(page.getByLabel("Destination", { exact: true })).toHaveValue("");
});
test("delayed save locks record selection and duplicate submission, then reconciles A", async ({
  page,
}) => {
  let writes = 0,
    release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/travel/trips/a", async (route) => {
    writes++;
    await gate;
    return reply(route, trip("a", "Lisbon revised", 2));
  });
  await page.goto("/travel");
  await page.getByRole("button", { name: "Lisbon · 3 days" }).click();
  await page.getByLabel("Destination", { exact: true }).fill("Lisbon revised");
  await page.getByRole("button", { name: "Revise plan" }).click();
  await expect(
    page.getByRole("button", { name: "Berlin · 3 days" }),
  ).toBeDisabled();
  await expect(page.getByLabel("Destination", { exact: true })).toBeDisabled();
  await page
    .locator("form.feature-card")
    .evaluate((form) => (form as HTMLFormElement).requestSubmit());
  expect(writes).toBe(1);
  release();
  await expect(
    page.getByRole("heading", { name: "Lisbon revised · revision 2" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Berlin · 3 days" }).click();
  await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
    "Berlin",
  );
  expect(writes).toBe(1);
});
test("failed save keeps all edited fields and dirty navigation", async ({
  page,
}) => {
  await page.route("**/api/v1/travel/trips/a", (route) =>
    reply(route, { error: { message: "Synthetic save failure" } }, 503),
  );
  await page.goto("/travel");
  await page.getByRole("button", { name: "Lisbon · 3 days" }).click();
  await page
    .getByLabel("Destination", { exact: true })
    .fill("Preserve on failure");
  await page
    .getByLabel("Interests and preferences")
    .fill("Preserve these details");
  await page.getByRole("button", { name: "Revise plan" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Synthetic save failure",
  );
  await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
    "Preserve on failure",
  );
  await expect(page.getByLabel("Interests and preferences")).toHaveValue(
    "Preserve these details",
  );
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "New trip" }).click();
  await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
    "Preserve on failure",
  );
});
for (const sameUser of [true, false]) {
  test(`expired session: ${sameUser ? "same" : "different"} account, no automatic replay`, async ({
    page,
  }) => {
    let writes = 0;
    await page.route("**/api/v1/travel/trips/a", (route) => {
      writes++;
      return reply(route, { error: { message: "Session expired" } }, 401);
    });
    await page.route("**/api/v1/auth/login", (route) =>
      reply(route, { id: sameUser ? "synthetic-user-a" : "synthetic-user-b" }),
    );
    await page.goto("/travel");
    await page.getByRole("button", { name: "Lisbon · 3 days" }).click();
    await page
      .getByLabel("Destination", { exact: true })
      .fill("Owner A private draft");
    await page.getByRole("button", { name: "Revise plan" }).click();
    await expect(
      page.getByText("Your session expired or could not be verified.", {
        exact: false,
      }),
    ).toBeVisible();
    await expect(page.getByLabel("Destination", { exact: true })).toBeHidden();
    await page
      .getByLabel("Email", { exact: true })
      .fill("synthetic@example.test");
    await page
      .getByLabel("Password", { exact: true })
      .fill("Synthetic-only-password");
    await page.getByRole("button", { name: "Sign in and continue" }).click();
    await expect(page.getByLabel("Destination", { exact: true })).toHaveValue(
      sameUser ? "Owner A private draft" : "",
    );
    expect(writes).toBe(1);
  });
}

test("late optional Docs membership denial cannot expire a newly authenticated workspace", async ({
  page,
}) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/auth/me", (route) =>
    reply(route, { error: { message: "Sign in" } }, 401),
  );
  await page.route("**/api/v1/documentation/access", async (route) => {
    await gate;
    return reply(
      route,
      { error: { message: "Optional membership unavailable" } },
      401,
    );
  });
  await page.goto("/travel");
  await page
    .getByLabel("Email", { exact: true })
    .fill("synthetic@example.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("Synthetic-only-password");
  await page.getByRole("button", { name: "Sign in and continue" }).click();
  await expect(page.getByLabel("Destination", { exact: true })).toBeVisible();
  release();
  await expect(
    page.getByRole("button", { name: "Sign in and continue" }),
  ).toHaveCount(0);
  await page
    .getByLabel("Destination", { exact: true })
    .fill("Current session remains usable");
  await expect(page.getByLabel("Destination", { exact: true })).toBeVisible();
});

test("a temporary usability draft restores the baseline without bypassing navigation protection", async ({page}) => {
  const {createRequire} = await import("node:module");
  const {withTemporaryDraft} = createRequire(process.cwd() + "/package.json")("../../../scripts/usability-draft.cjs");
  await page.goto("/travel");
  const destination = page.getByLabel("Destination", {exact:true});
  await expect(destination).toBeEnabled();
  const baseline = await destination.inputValue();
  let observedEditable = false, dialogs = 0;
  page.on("dialog", async dialog => { dialogs++; await dialog.dismiss(); });
  await withTemporaryDraft(destination, async () => {
    await expect(destination).toHaveValue("Unsent synthetic timing draft");
    observedEditable = true;
  });
  expect(observedEditable).toBe(true);
  await expect(destination).toHaveValue(baseline);
  await expect(withTemporaryDraft(destination, () => {
    throw new Error("Synthetic timing failure");
  })).rejects.toThrow("Synthetic timing failure");
  await expect(destination).toHaveValue(baseline);
  await page.getByRole("navigation", {name:"AI workspace"}).getByRole("link", {name:"Knowledge", exact:true}).click();
  await expect(page).toHaveURL(/\/knowledge$/);
  expect(dialogs).toBe(0);
  await page.getByRole("navigation", {name:"AI workspace"}).getByRole("link", {name:"Travel", exact:true}).click();
  await expect(destination).toBeEnabled();
  await destination.fill("An actual unsaved draft");
  await page.getByRole("navigation", {name:"AI workspace"}).getByRole("link", {name:"Knowledge", exact:true}).click();
  await expect(page).toHaveURL(/\/travel$/);
  expect(dialogs).toBe(1);
  await expect(destination).toHaveValue("An actual unsaved draft");
});
