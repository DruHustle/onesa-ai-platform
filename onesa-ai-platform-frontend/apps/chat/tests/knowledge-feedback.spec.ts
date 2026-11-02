import { test, expect, type Page, type Route } from "@playwright/test";

// UI-only transport fixtures. These tests do not qualify uploads, retrieval or a real model.
const sampleDocument = {
  id: "synthetic-document",
  title: "Synthetic guide.txt",
  embedding_version: "lexical:onesa-lexical-256-v1:1",
};
const source = {
  document_id: sampleDocument.id,
  title: sampleDocument.title,
  chunk: 0,
  text: "Synthetic source passage for interface feedback only.",
};
const reply = (route: Route, body: unknown, status = 200) =>
  route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });

function gate() {
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { pending, release };
}

async function setup(page: Page, items: (typeof sampleDocument)[] = []) {
  await page.route("**/api/**", (route) =>
    reply(
      route,
      {
        error: {
          code: "fixture_missing",
          message: "No synthetic fixture for this endpoint",
        },
      },
      503,
    ),
  );
  await page.route("**/api/v1/auth/onesa/config", (route) =>
    reply(route, { enabled: false, account_url: null }),
  );
  await page.route("**/api/v1/auth/me", (route) =>
    reply(route, { id: "synthetic-knowledge-owner" }),
  );
  await page.route("**/api/v1/documentation/access", (route) =>
    reply(route, { engineering: false }),
  );
  await page.route("**/api/v1/twins/readiness", (route) =>
    reply(route, { enabled: false }),
  );
  await page.route("**/api/v1/cybersecurity/readiness", (route) =>
    reply(route, { enabled: false }),
  );
  await page.route("**/api/v1/industrial/assets", (route) =>
    reply(route, {}, 404),
  );
  await page.route("**/api/v1/knowledge/documents{,?*}", (route) =>
    reply(route, { items, next_cursor: null }),
  );
}

test.beforeEach(async ({ baseURL }) => {
  if (
    !["localhost", "127.0.0.1", "[::1]"].includes(
      new URL(baseURL ?? "http://localhost:3100").hostname,
    )
  ) {
    throw new Error(
      "Knowledge UI fixtures require an isolated loopback frontend; hosted targets are forbidden.",
    );
  }
});

for (const outcome of ["success", "failure"] as const) {
  test(`upload ${outcome}: wait for completion, prevent duplicates and preserve truthful feedback`, async ({
    page,
  }) => {
    await setup(page);
    const completion = gate();
    let starts = 0,
      completes = 0,
      cleanups = 0,
      uploaded = false;
    await page.route("**/api/v1/knowledge/documents{,?*}", (route) =>
      reply(route, { items: uploaded ? [sampleDocument] : [] }),
    );
    await page.route("**/api/v1/knowledge/uploads", (route) => {
      starts++;
      return reply(route, { id: "synthetic-upload" });
    });
    await page.route(
      "**/api/v1/knowledge/uploads/synthetic-upload/chunks",
      (route) => reply(route, {}),
    );
    await page.route(
      "**/api/v1/knowledge/uploads/synthetic-upload/complete",
      async (route) => {
        completes++;
        await completion.pending;
        uploaded = outcome === "success";
        return outcome === "success"
          ? reply(route, sampleDocument)
          : reply(
              route,
              {
                error: {
                  code: "unavailable",
                  message: "Synthetic upload completion unavailable",
                },
              },
              503,
            );
      },
    );
    await page.route(
      "**/api/v1/knowledge/uploads/synthetic-upload",
      (route) => {
        expect(route.request().method()).toBe("DELETE");
        cleanups++;
        return route.fulfill({ status: 204 });
      },
    );
    try {
      await page.goto("/knowledge");
      const file = page.getByLabel("Document (.txt or .pdf, up to 5 MiB)", {
        exact: true,
      });
      await file.setInputFiles({
        name: sampleDocument.title,
        mimeType: "text/plain",
        buffer: Buffer.from("Synthetic feedback fixture."),
      });
      await page
        .getByRole("button", { name: "Upload document", exact: true })
        .click();
      await expect.poll(() => completes).toBe(1);
      await expect(
        page.getByRole("button", { name: "Uploading document…", exact: true }),
      ).toBeDisabled();
      await expect(
        page.getByRole("status").filter({ hasText: "Uploaded “" }),
      ).toHaveCount(0);
      await page
        .getByRole("form", { name: "Add a document" })
        .evaluate((form) => (form as HTMLFormElement).requestSubmit());
      expect(starts).toBe(1);
      completion.release();
      await expect(
        page.getByRole("button", { name: "Upload document", exact: true }),
      ).toBeEnabled();
      if (outcome === "success") {
        await expect(
          page
            .getByRole("status")
            .filter({ hasText: `Uploaded “${sampleDocument.title}”` }),
        ).toBeVisible();
        await expect(
          page.getByRole("heading", {
            name: sampleDocument.title,
            exact: true,
          }),
        ).toBeVisible();
        await expect
          .poll(() =>
            file.evaluate((input) => (input as HTMLInputElement).files?.length),
          )
          .toBe(0);
        expect(cleanups).toBe(0);
      } else {
        await expect(page.locator("main").getByRole("alert")).toContainText(
          "Synthetic upload completion unavailable",
        );
        await expect(
          page.getByRole("status").filter({ hasText: "Uploaded “" }),
        ).toHaveCount(0);
        expect(
          await file.evaluate(
            (input) => (input as HTMLInputElement).files?.[0]?.name,
          ),
        ).toBe(sampleDocument.title);
        expect(cleanups).toBe(1);
      }
      expect(starts).toBe(1);
      expect(completes).toBe(1);
    } finally {
      completion.release();
    }
  });
}

test("an expired upload preserves the file and query through same-account sign-in without replay", async ({
  page,
}) => {
  await setup(page);
  let starts = 0,
    completes = 0,
    cleanups = 0,
    uploaded = false;
  const expired = {
    error: {
      code: "unauthenticated",
      message: "Synthetic session expired during upload",
    },
  };
  await page.route("**/api/v1/auth/login", (route) =>
    reply(route, { id: "synthetic-knowledge-owner" }),
  );
  await page.route("**/api/v1/knowledge/documents{,?*}", (route) =>
    reply(route, { items: uploaded ? [sampleDocument] : [] }),
  );
  await page.route("**/api/v1/knowledge/uploads", (route) => {
    starts++;
    return reply(route, { id: "synthetic-expired-upload" });
  });
  await page.route(
    "**/api/v1/knowledge/uploads/synthetic-expired-upload/chunks",
    (route) => reply(route, {}),
  );
  await page.route(
    "**/api/v1/knowledge/uploads/synthetic-expired-upload/complete",
    (route) => {
      completes++;
      if (completes === 1) return reply(route, expired, 401);
      uploaded = true;
      return reply(route, sampleDocument);
    },
  );
  await page.route(
    "**/api/v1/knowledge/uploads/synthetic-expired-upload",
    (route) => {
      expect(route.request().method()).toBe("DELETE");
      cleanups++;
      return reply(route, expired, 401);
    },
  );
  await page.goto("/knowledge");
  await page.evaluate(() => {
    document.documentElement.dataset.syntheticSessionExpiries = "0";
    window.addEventListener("onesa-session-expired", () => {
      const node = document.documentElement;
      node.dataset.syntheticSessionExpiries = String(
        Number(node.dataset.syntheticSessionExpiries) + 1,
      );
    });
  });
  const file = page.getByLabel("Document (.txt or .pdf, up to 5 MiB)", {
    exact: true,
  });
  const query = page.getByLabel("Search your documents", { exact: true });
  await query.fill("Keep this document question");
  await file.setInputFiles({
    name: sampleDocument.title,
    mimeType: "text/plain",
    buffer: Buffer.from("Synthetic session recovery fixture."),
  });
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  const signIn = page.getByRole("form", { name: "Sign in", exact: true });
  await expect(signIn).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Your session expired or could not be verified.",
  );
  await expect.poll(() => cleanups).toBe(1);
  await expect(page.locator("html")).toHaveAttribute(
    "data-synthetic-session-expiries",
    "1",
  );
  await signIn
    .getByLabel("Email", { exact: true })
    .fill("synthetic@example.test");
  await signIn
    .getByLabel("Password", { exact: true })
    .fill("Synthetic-only-password");
  await signIn
    .getByRole("button", { name: "Sign in and continue", exact: true })
    .click();
  await expect(signIn).toHaveCount(0);
  await expect(query).toHaveValue("Keep this document question");
  await expect(file).toBeVisible();
  expect(
    await file.evaluate(
      (input) => (input as HTMLInputElement).files?.[0]?.name,
    ),
  ).toBe(sampleDocument.title);
  // Recovery restores the task; it never starts another upload automatically.
  const upload = page.getByRole("button", {
    name: "Upload document",
    exact: true,
  });
  await expect(upload).toBeEnabled();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Synthetic session expired during upload",
  );
  await expect(signIn).toHaveCount(0);
  await expect(
    page.getByRole("status").filter({ hasText: "Uploaded “" }),
  ).toHaveCount(0);
  expect(starts).toBe(1);
  expect(completes).toBe(1);

  await upload.click();
  await expect(
    page.getByRole("status").filter({
      hasText: `Uploaded “${sampleDocument.title}”`,
    }),
  ).toBeVisible();
  await expect(query).toHaveValue("Keep this document question");
  expect(starts).toBe(2);
  expect(completes).toBe(2);
  expect(cleanups).toBe(1);
  // Both the complete and cleanup401s belong to one expiry notification.
  await expect(page.locator("html")).toHaveAttribute(
    "data-synthetic-session-expiries",
    "1",
  );
});

test("a delayed zero-result search names the submitted query and preserves a newer editable draft", async ({
  page,
}) => {
  await setup(page);
  const search = gate();
  const submitted: string[] = [];
  await page.route("**/api/v1/knowledge/search", async (route) => {
    submitted.push(route.request().postDataJSON().query);
    await search.pending;
    return reply(route, { sources: [] });
  });
  try {
    await page.goto("/knowledge");
    const input = page.getByLabel("Search your documents", { exact: true });
    await input.fill("   ");
    await expect(
      page.getByRole("button", { name: "Search", exact: true }),
    ).toBeDisabled();
    expect(submitted).toEqual([]);
    await input.fill("battery temperature");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: "Searching for “battery temperature”" }),
    ).toBeVisible();
    await input.fill("maintenance interval");
    await input.evaluate((element) =>
      (element as HTMLInputElement).form!.requestSubmit(),
    );
    expect(submitted).toEqual(["battery temperature"]);
    search.release();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: "No passages found for “battery temperature”" }),
    ).toBeVisible();
    await expect(input).toHaveValue("maintenance interval");
    await expect(
      page.getByRole("button", { name: "Search", exact: true }),
    ).toBeEnabled();
  } finally {
    search.release();
  }
});

test("a new failed search clears older results and keeps the query without suggesting reauthentication", async ({
  page,
}) => {
  await setup(page, [sampleDocument]);
  let requests = 0;
  const failed = gate();
  await page.route("**/api/v1/knowledge/search", async (route) => {
    requests++;
    if (requests === 1) return reply(route, { sources: [source] });
    await failed.pending;
    return reply(
      route,
      {
        error: {
          code: "unavailable",
          message: "Synthetic search temporarily unavailable",
        },
      },
      503,
    );
  });
  try {
    await page.goto("/knowledge");
    const input = page.getByLabel("Search your documents", { exact: true });
    await input.fill("first question");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByText(source.text, { exact: true })).toBeVisible();
    await input.fill("second question");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByText(source.text, { exact: true })).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Searching…", exact: true }),
    ).toBeDisabled();
    failed.release();
    const error = page.locator("main").getByRole("alert");
    await expect(error).toContainText("Search for “second question” failed.");
    await expect(error).toContainText(
      "Synthetic search temporarily unavailable",
    );
    await expect(error).not.toContainText(/sign in/i);
    await expect(input).toHaveValue("second question");
    await expect(
      page.getByRole("button", { name: "Search", exact: true }),
    ).toBeEnabled();
    expect(requests).toBe(2);
  } finally {
    failed.release();
  }
});

for (const action of ["delete", "reindex"] as const) {
  test(`${action} prevents pending search and preview responses from restoring obsolete content`, async ({
    page,
  }) => {
    await setup(page, [sampleDocument]);
    const search = gate(),
      preview = gate(),
      mutation = gate();
    const searchDone = gate(),
      previewDone = gate();
    let searches = 0,
      previews = 0,
      writes = 0,
      deleted = false;
    await page.route("**/api/v1/knowledge/documents{,?*}", (route) =>
      reply(route, { items: deleted ? [] : [sampleDocument] }),
    );
    await page.route("**/api/v1/knowledge/search", async (route) => {
      searches++;
      await search.pending;
      try {
        await reply(route, { sources: [source] });
      } catch {
        /* The mutation cancelled this old request. */
      } finally {
        searchDone.release();
      }
    });
    await page.route(
      "**/api/v1/knowledge/documents/synthetic-document",
      async (route) => {
        if (route.request().method() === "DELETE") {
          writes++;
          await mutation.pending;
          deleted = true;
          return route.fulfill({ status: 204 });
        }
        previews++;
        await preview.pending;
        try {
          await reply(route, {
            ...sampleDocument,
            text: "Obsolete synthetic preview text.",
          });
        } catch {
          /* Cancelled old request. */
        } finally {
          previewDone.release();
        }
      },
    );
    await page.route(
      "**/api/v1/knowledge/documents/synthetic-document/reindex",
      async (route) => {
        writes++;
        await mutation.pending;
        return reply(route, sampleDocument);
      },
    );
    try {
      await page.goto("/knowledge");
      await page
        .getByLabel("Search your documents", { exact: true })
        .fill("old query");
      await page.getByRole("button", { name: "Search", exact: true }).click();
      await page
        .getByRole("button", { name: "Preview extracted text", exact: true })
        .click();
      await expect.poll(() => [searches, previews]).toEqual([1, 1]);
      if (action === "delete") page.once("dialog", (dialog) => dialog.accept());
      const name =
        action === "delete" ? "Delete document" : "Rebuild search index";
      await page.getByRole("button", { name, exact: true }).click();
      await expect.poll(() => writes).toBe(1);
      await expect(
        page.getByRole("button", {
          name:
            action === "delete"
              ? "Deleting document…"
              : "Rebuilding search index…",
          exact: true,
        }),
      ).toBeDisabled();
      mutation.release();
      await expect(
        page.getByRole("status").filter({
          hasText:
            action === "delete" ? "Deleted “" : "Document search index rebuilt",
        }),
      ).toBeVisible();
      search.release();
      preview.release();
      await Promise.all([searchDone.pending, previewDone.pending]);
      await expect(page.getByText(source.text, { exact: true })).toHaveCount(0);
      await expect(
        page.getByText("Obsolete synthetic preview text.", { exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByRole("heading", {
          name: `Preview: ${sampleDocument.title}`,
          exact: true,
        }),
      ).toHaveCount(0);
      await expect(
        page
          .getByRole("status")
          .filter({ hasText: "Previous search results were cleared" }),
      ).toBeVisible();
      await expect(
        page.getByLabel("Search your documents", { exact: true }),
      ).toHaveValue("old query");
      expect(writes).toBe(1);
    } finally {
      search.release();
      preview.release();
      mutation.release();
    }
  });
}

test("empty and failed search feedback remains usable at 320 CSS pixels and enlarged text", async ({
  page,
}) => {
  await setup(page);
  await page.setViewportSize({ width: 320, height: 900 });
  await page.route("**/api/v1/knowledge/search", (route) =>
    reply(
      route,
      {
        error: { code: "unavailable", message: "Synthetic search unavailable" },
      },
      503,
    ),
  );
  await page.goto("/knowledge");
  await expect(
    page.getByRole("heading", { name: "No documents yet.", exact: true }),
  ).toBeVisible();
  const input = page.getByLabel("Search your documents", { exact: true });
  await input.fill(
    "A long synthetic question about a maintenance schedule and supporting documentation",
  );
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Synthetic search unavailable",
  );
  await input.focus();
  for (const colorScheme of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme });
    await expect(input).toBeFocused();
    await expect(input).toHaveValue(
      "A long synthetic question about a maintenance schedule and supporting documentation",
    );
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth + 1,
      ),
    ).toBe(true);
  }
  // This is 200% text sizing, not a claim of native browser zoom verification.
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth + 1,
    ),
  ).toBe(true);
  await expect(input).toBeFocused();
});
