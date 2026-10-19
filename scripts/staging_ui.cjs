/* Actual protected Preview UI acceptance; run-scoped synthetic credentials remain private. */
const fs = require("node:fs"),
  path = require("node:path");
const { createRequire } = require("node:module");
const { createHash } = require("node:crypto");
const { safeFailureDiagnostics } = require("./ui_failure_diagnostics.cjs");
const { withTemporaryDraft } = require("./usability-draft.cjs");
const requireChat = createRequire(
  path.resolve("onesa-ai-platform-frontend/apps/chat/package.json"),
);
const { chromium, expect } = requireChat("@playwright/test");
const { default: AxeBuilder } = requireChat("@axe-core/playwright");
const oracle = process.env.ONESA_ORACLE_QUALIFICATION_CONTEXT
  ? require("./oracle_context.cjs").loadContext(process.env.ONESA_ORACLE_QUALIFICATION_CONTEXT)
  : null;
const sourceIdentity = () => oracle ? {
  candidate_commit: oracle.candidate_commit,
  workflow_run_id: 0,
  ci_run_id: oracle.ci_run_id,
  qualification_id: oracle.qualification_id,
  execution_context: oracle.execution_context,
} : {
  candidate_commit: process.env.GITHUB_SHA,
  workflow_run_id: Number(process.env.GITHUB_RUN_ID),
};
const outputDirectory = () => oracle ? oracle.output_dir : process.env.RUNNER_TEMP;

async function verifyIcons(page, origin, bypass) {
  const root = "onesa-ai-platform-frontend/apps/chat/public/brand/icons/v1";
  const manifest = JSON.parse(
    fs.readFileSync(path.join(root, "sources.json"), "utf8"),
  );
  const product = manifest.products[0];
  const icons = [
    ["onesa-ai.svg", 'link[rel="icon"][type="image/svg+xml"]', "any"],
    ["onesa-ai-180.png", 'link[rel="apple-touch-icon"]', "180x180"],
  ];
  for (const [name, selector, sizes] of icons) {
    await expect(page.locator(selector)).toHaveAttribute(
      "href",
      "/brand/icons/v1/" + name,
    );
    await expect(page.locator(selector)).toHaveAttribute("sizes", sizes);
  }
  const observed = [];
  for (const name of ["onesa-ai.svg", "onesa-ai-180.png", "onesa-ai.ico"]) {
    const source = product.files.find((file) => file.name === name);
    const url = name.endsWith(".ico")
      ? "/favicon.ico"
      : "/brand/icons/v1/" + name;
    const response = await page.request.get(origin + url, {
      headers: { "x-vercel-protection-bypass": bypass },
    });
    expect(response.status()).toBe(200);
    const bytes = await response.body();
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(
      source.sha256,
    );
    expect(
      name.endsWith(".ico")
        ? ["image/x-icon", "image/vnd.microsoft.icon"]
        : [source.mime],
    ).toContain(response.headers()["content-type"].split(";")[0]);
    observed.push({ path: url, sha256: source.sha256, status: 200 });
  }
  return observed;
}

function fixtures() {
  const modern = oracle || process.env.STAGING_FIXTURE_MODE === "temporary";
  let value;
  if (modern) {
    const file = oracle ? oracle.fixture_file : path.join(
      process.env.RUNNER_TEMP,
      "onesa-private-staging-fixtures.json",
    );
    if (fs.statSync(file).mode & 0o077)
      throw new Error("Private fixture permissions required");
    value = JSON.parse(fs.readFileSync(file, "utf8"));
    if (
      value.candidate_commit !== (oracle ? oracle.candidate_commit : process.env.GITHUB_SHA) ||
      String(value.run_id) !== String(oracle ? oracle.ci_run_id : process.env.GITHUB_RUN_ID)
    )
      throw new Error("Fixture source mismatch");
  } else value = JSON.parse(process.env.STAGING_FIXTURES_JSON || "null");
  if (
    !value ||
    value.scope !== "approved-synthetic-staging" ||
    value.project_id !== (oracle ? oracle.project_id : process.env.VERCEL_PROJECT_ID) ||
    !Array.isArray(value.users) ||
    value.users.length !== 2
  )
    throw new Error("Approved fixture binding required");
  if (
    value.users.some(
      (user) =>
        typeof user.email !== "string" || typeof user.password !== "string",
    )
  )
    throw new Error("Private synthetic credentials required");
  return value.users;
}

async function measureUsability(browser, origin, bypass, account, pageErrors, observeCheck) {
  const measurements = [];
  for (const mode of ["normal", "slow-mobile"]) {
    const context = await browser.newContext({
      viewport:
        mode === "normal"
          ? { width: 1440, height: 900 }
          : { width: 390, height: 844 },
      locale: "en-US",
      colorScheme: "light",
    });
    try {
      await context.addCookies([
        { name: "onesa_ui_locale", value: "en", url: origin },
      ]);
      await context.route("**/*", async (route) => {
        const request = route.request();
        await route.continue({
          headers: {
            ...request.headers(),
            ...(new URL(request.url()).origin === origin
              ? { "x-vercel-protection-bypass": bypass }
              : {}),
          },
        });
      });
      const page = await context.newPage();
      page.on("pageerror", () => pageErrors.push("pageerror"));
      const session = await context.newCDPSession(page);
      await session.send("Network.enable");
      await session.send("Network.setCacheDisabled", { cacheDisabled: true });
      if (mode === "slow-mobile") {
        await session.send("Network.emulateNetworkConditions", {
          offline: false,
          latency: 150,
          downloadThroughput: 200000,
          uploadThroughput: 93750,
        });
        await session.send("Emulation.setCPUThrottlingRate", { rate: 4 });
      }
      const started = performance.now();
      observeCheck("usability_sign_in_visible");
      const response = await page.goto(origin, { waitUntil: "commit" });
      expect(response.status()).toBe(200);
      await expect(
        page.getByRole("heading", { name: "Welcome back", exact: true }),
      ).toBeVisible({ timeout: 20000 });
      await page.waitForFunction(
        () => performance.getEntriesByName("first-contentful-paint").length > 0,
      );
      const signInVisible = Math.round(performance.now() - started);
      await page.getByLabel("Email", { exact: true }).fill(account.email);
      await page.getByLabel("Password", { exact: true }).fill(account.password);
      const draftEditable = Math.round(performance.now() - started);
      const submit = page.getByRole("button", { name: "Sign in", exact: true });
      observeCheck("usability_submission_ready");
      await expect(submit).toBeEnabled({ timeout: 20000 });
      const submissionReady = Math.round(performance.now() - started);
      const signInStarted = performance.now();
      observeCheck("usability_sign_in_complete");
      await submit.click();
      await expect(page.getByLabel("Message Onesa AI")).toBeEnabled({
        timeout: 20000,
      });
      const signInToComposer = Math.round(performance.now() - signInStarted);
      const navigation = [];
      for (const [route, label, field] of [
        ["/knowledge", "Knowledge", "Search your documents"],
        ["/agents", "Agents", "Text to analyze"],
        ["/travel", "Travel", "Destination"],
        ["/", "Chat", "Message Onesa AI"],
      ]) {
        if (
          await page
            .getByLabel("Toggle conversations", { exact: true })
            .isVisible()
        )
          await page
            .getByLabel("Toggle conversations", { exact: true })
            .click();
        const before = performance.now();
        observeCheck("usability_navigation_url");
        await page.getByRole("link", { name: label, exact: true }).click();
        await expect(page).toHaveURL(origin + route);
        const input = page.getByLabel(field, { exact: true });
        observeCheck("usability_field_editable");
        await expect(input).toBeEnabled({ timeout: 20000 });
        await withTemporaryDraft(input, () => {
          navigation.push({
            route,
            draft_usable_ms: Math.round(performance.now() - before),
          });
        });
      }
      const resources = await page.evaluate(() => {
        const navigation = performance.getEntriesByType("navigation")[0];
        const resources = performance.getEntriesByType("resource");
        const scripts = resources.filter((item) =>
          new URL(item.name).pathname.endsWith(".js"),
        );
        return {
          document_ttfb_ms: Math.round(
            navigation.responseStart - navigation.requestStart,
          ),
          first_contentful_paint_ms: Math.round(
            performance.getEntriesByName("first-contentful-paint")[0]
              ?.startTime ?? 0,
          ),
          script_encoded_body_bytes: scripts.reduce(
            (total, item) => total + item.encodedBodySize,
            0,
          ),
          script_decoded_body_bytes: scripts.reduce(
            (total, item) => total + item.decodedBodySize,
            0,
          ),
          api_samples: resources
            .filter((item) =>
              [
                "/api/v1/auth/me",
                "/api/v1/auth/login",
                "/api/v1/models",
                "/api/v1/conversations",
                "/api/v1/knowledge/documents",
                "/api/v1/agents/runs",
                "/api/v1/travel/trips",
                "/api/v1/documentation/access",
              ].includes(new URL(item.name).pathname),
            )
            .slice(0, 30)
            .map((item) => ({
              path: new URL(item.name).pathname,
              start_ms: Math.round(item.startTime),
              duration_ms: Math.round(item.duration),
            })),
        };
      });
      measurements.push({
        mode,
        sign_in_visible_ms: signInVisible,
        credential_draft_editable_ms: draftEditable,
        submission_ready_ms: submissionReady,
        sign_in_to_composer_ms: signInToComposer,
        navigation,
        ...resources,
      });
    } finally {
      await context.close();
    }
  }
  return {
    scope: "actual protected Preview; same approved synthetic fixture lifetime",
    trials_per_mode: 1,
    controls: {
      slow_mobile: {
        latency_ms: 150,
        download_mbps: 1.6,
        upload_mbps: 0.75,
        cpu_slowdown: 4,
      },
    },
    measurements,
  };
}

async function main() {
  if (
    !oracle && (process.env.GITHUB_REF !== "refs/heads/staging" ||
    process.env.GITHUB_REPOSITORY !== "DruHustle/onesa-ai-platform")
  )
    throw new Error("Only AI staging is authorized");
  const origin = oracle ? oracle.frontend_origin : fs.readFileSync("/tmp/vercel-url.txt", "utf8").trim();
  const bypass = process.env.VERCEL_AUTOMATION_BYPASS_SECRET;
  if (!bypass || !/^https:\/\/[a-z0-9-]+\.vercel\.app$/.test(origin))
    throw new Error("Verified protected Preview required");
  const accounts = fixtures(),
    browser = await chromium.launch(),
    views = [],
    workflowChecks = {};
  let phase = "authenticated-layouts",
    identityIcons;
  let draftCheck = { phase: "", check: "not-recorded" };
  const observeDraftCheck = (check) => { draftCheck = { phase, check }; };
  const pageErrors = [];
  const authenticationStatuses = [];
  try {
    for (const [name, width, height] of [
      ["desktop", 1440, 900],
      ["tablet", 768, 1024],
      ["mobile", 320, 844],
    ])
      for (const mode of ["light", "dark"]) {
        const context = await browser.newContext({
          viewport: { width, height },
          locale: "en-US",
          colorScheme: mode,
          reducedMotion: "reduce",
        });
        await context.addCookies([
          { name: "onesa_ui_locale", value: "en", url: origin },
        ]);
        await context.addInitScript(
          (hour) => {
            Date.prototype.getHours = () => hour;
          },
          mode === "light" ? 23 : 12,
        );
        await context.route("**/*", async (route) => {
          const request = route.request();
          await route.continue({
            headers: {
              ...request.headers(),
              ...(new URL(request.url()).origin === origin
                ? { "x-vercel-protection-bypass": bypass }
                : {}),
            },
          });
        });
        const page = await context.newPage();
        page.on("pageerror", () => pageErrors.push("pageerror"));
        const authenticationStarted = performance.now();
        page.on("response", (response) => {
          const url = new URL(response.url());
          if (
            url.origin === origin &&
            ["/api/v1/auth/me", "/api/v1/auth/login"].includes(url.pathname)
          )
            authenticationStatuses.push({
              viewport: name,
              mode,
              path: url.pathname,
              status: response.status(),
              elapsed_ms: Math.round(performance.now() - authenticationStarted),
            });
        });
        await page.goto(origin, { waitUntil: "networkidle" });
        if (!identityIcons) {
          phase = "metadata-and-icons";
          identityIcons = await verifyIcons(page, origin, bypass);
        }
        phase = "authenticated-login:" + name + ":" + mode;
        await page.getByLabel("Email", { exact: true }).fill(accounts[0].email);
        await page
          .getByLabel("Password", { exact: true })
          .fill(accounts[0].password);
        await page
          .getByRole("button", { name: "Sign in", exact: true })
          .click();
        await expect(page.getByLabel("Message Onesa AI")).toBeVisible();
        for (const route of [
          "/",
          "/knowledge",
          "/agents",
          "/travel",
          "/settings",
          "/recovery",
          "/invitation",
        ]) {
          phase = "layout:" + name + ":" + route + ":" + mode;
          const response = await page.goto(origin + route, {
            waitUntil: "networkidle",
          });
          if (!response || response.status() !== 200)
            throw new Error("Interface route failed");
          await expect(page.locator("main")).toBeVisible();
          expect(
            await page.evaluate(
              () => getComputedStyle(document.documentElement).colorScheme,
            ),
          ).toBe(mode);
          await expect(page.locator(".appearance-control")).toHaveCount(0);
          await expect(page.locator(".environment-context")).toHaveText(
            "STAGING · Onesa AI Platform",
          );
          expect(
            await page.evaluate(
              () => document.documentElement.scrollWidth <= innerWidth + 2,
            ),
          ).toBe(true);
          const violations = (
            await new AxeBuilder({ page })
              .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
              .analyze()
          ).violations;
          expect(violations.map((item) => item.id)).toEqual([]);
          views.push({
            viewport: name,
            width,
            route,
            mode,
            overflow: false,
            axe_violations: 0,
            system_scheme: mode,
          });
        }
        for (const [route, label] of [
          ["/", "Message Onesa AI"],
          ["/knowledge", "Search your documents"],
          ["/agents", "Text to analyze"],
          ["/travel", "Destination"],
        ]) {
          phase = "live-draft:" + name + ":" + route + ":" + mode;
          observeDraftCheck("navigate");
          await page.goto(origin + route, { waitUntil: "networkidle" });
          const field = page.getByLabel(label, { exact: true });
          observeDraftCheck("field_visible");
          await expect(field).toBeVisible();
          observeDraftCheck("fill_draft");
          await field.fill("Unsent synthetic draft");
          observeDraftCheck("focus_draft");
          await field.focus();
          observeDraftCheck("session_before");
          const before = (await context.cookies(origin)).find(
            (cookie) => cookie.name === "onesa_session",
          )?.value;
          expect(typeof before).toBe("string");
          let apiRequests = 0;
          const observe = (request) => {
            if (new URL(request.url()).pathname.startsWith("/api/"))
              apiRequests++;
          };
          page.on("request", observe);
          observeDraftCheck("change_system_preference");
          await page.emulateMedia({
            colorScheme: mode === "light" ? "dark" : "light",
          });
          observeDraftCheck("observe_system_preference");
          expect(
            await page.evaluate(
              () => getComputedStyle(document.documentElement).colorScheme,
            ),
          ).toBe(mode === "light" ? "dark" : "light");
          observeDraftCheck("draft_preserved");
          await expect(field).toHaveValue("Unsent synthetic draft");
          observeDraftCheck("focus_preserved");
          await expect(field).toBeFocused();
          observeDraftCheck("session_preserved");
          expect(
            (await context.cookies(origin)).find(
              (cookie) => cookie.name === "onesa_session",
            )?.value,
          ).toBe(before);
          observeDraftCheck("no_appearance_api_requests");
          expect(apiRequests).toBe(0);
          page.off("request", observe);
          observeDraftCheck("no_stored_appearance");
          expect(
            await page.evaluate(() =>
              Object.keys(localStorage).filter((key) =>
                /theme|appearance/i.test(key),
              ),
            ),
          ).toEqual([]);
          observeDraftCheck("restore_system_preference");
          await page.emulateMedia({ colorScheme: mode });
        }
        expect(
          (
            await context.request.get(origin + "/api/v1/auth/me", {
              headers: { "x-vercel-protection-bypass": bypass },
            })
          ).status(),
        ).toBe(200);
        await context.close();
      }
    workflowChecks.hosted_all_route_modes_and_accessibility = "PASS";
    workflowChecks.live_drafts_focus_session_and_no_mode_requests = "PASS";
    phase = "actual-stream-mode-and-stop";
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      colorScheme: "light",
    });
    await context.addCookies([
      { name: "onesa_ui_locale", value: "en", url: origin },
    ]);
    await context.route("**/*", async (route) => {
      const request = route.request();
      await route.continue({
        headers: {
          ...request.headers(),
          ...(new URL(request.url()).origin === origin
            ? { "x-vercel-protection-bypass": bypass }
            : {}),
        },
      });
    });
    const page = await context.newPage();
    page.on("pageerror", () => pageErrors.push("pageerror"));
    await page.goto(origin, { waitUntil: "networkidle" });
    await page.getByLabel("Email", { exact: true }).fill(accounts[1].email);
    await page
      .getByLabel("Password", { exact: true })
      .fill(accounts[1].password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    const input = page.getByLabel("Message Onesa AI");
    await expect(input).toBeVisible();
    let submissions = 0,
      conversation;
    page.on("request", (request) => {
      if (
        new URL(request.url()).pathname === "/api/v1/chat/completions" &&
        request.method() === "POST"
      ) {
        submissions++;
        conversation = request.postDataJSON().conversation_id;
      }
    });
    await input.fill(
      "Write a detailed explanation of vector similarity in 100 numbered paragraphs. Begin immediately and continue with detailed examples.",
    );
    await page.getByLabel("Send message", { exact: true }).click();
    const stop = page.getByRole("button", { name: "Stop", exact: true });
    await expect(stop).toBeEnabled({ timeout: 60000 });
    const before = (await context.cookies(origin)).find(
      (cookie) => cookie.name === "onesa_session",
    )?.value;
    expect(typeof before).toBe("string");
    await stop.focus();
    await page.emulateMedia({ colorScheme: "dark" });
    expect(
      await page.evaluate(
        () => getComputedStyle(document.documentElement).colorScheme,
      ),
    ).toBe("dark");
    await expect(stop).toBeFocused();
    await expect(stop).toBeEnabled();
    expect(submissions).toBe(1);
    expect(
      (await context.cookies(origin)).find(
        (cookie) => cookie.name === "onesa_session",
      )?.value,
    ).toBe(before);
    const cancellation = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname.endsWith("/cancel") &&
        response.request().method() === "POST",
    );
    await stop.click();
    expect((await cancellation).status()).toBe(204);
    await expect(stop).toHaveCount(0, { timeout: 15000 });
    expect(submissions).toBe(1);
    const csrf = (await context.cookies(origin)).find(
      (cookie) => cookie.name === "onesa_csrf",
    )?.value;
    const headers = {
      Origin: origin,
      "X-CSRF-Token": csrf,
      "x-vercel-protection-bypass": bypass,
    };
    expect(
      (
        await context.request.get(origin + "/api/v1/auth/me", { headers })
      ).status(),
    ).toBe(200);
    if (conversation)
      expect(
        (
          await context.request.delete(
            origin + "/api/v1/conversations/" + conversation,
            { headers },
          )
        ).status(),
      ).toBe(204);
    workflowChecks.actual_stream_mode_change_without_resubmission = "PASS";
    workflowChecks.actual_stop_and_session_preservation = "PASS";
    await context.close();
    phase = "bounded-usability-timing";
    const usability = await measureUsability(
      browser,
      origin,
      bypass,
      accounts[0],
      pageErrors,
      observeDraftCheck,
    );
    expect(pageErrors).toEqual([]);
    const report = {
      status: "PASS",
      ...sourceIdentity(),
      origin,
      browser: "chromium",
      views,
      authentication_statuses: authenticationStatuses,
      workflow_checks: workflowChecks,
      identity_icons: identityIcons,
      usability,
      real_hosted: true,
      synthetic_only: true,
      manual_safari_and_screen_reader: "NOT TESTED",
    };
    fs.writeFileSync(
      path.join(outputDirectory(), "hosted-ui.json"),
      JSON.stringify(report, null, 2),
    );
    console.log(
      JSON.stringify({
        status: report.status,
        views: views.length,
        workflow_checks: workflowChecks,
        usability,
        real_hosted: true,
        synthetic_only: true,
      }),
    );
  } catch (error) {
    console.error("Hosted UI failure phase: " + phase);
    console.error(
      "Hosted UI authentication statuses: " +
        JSON.stringify(authenticationStatuses),
    );
    fs.writeFileSync(
      path.join(outputDirectory(), "hosted-ui.json"),
      JSON.stringify({
        status: "FAIL",
        ...sourceIdentity(),
        failure_phase: phase,
        failure_diagnostics: safeFailureDiagnostics(
          error, draftCheck.phase === phase ? draftCheck.check : null,
        ),
        views,
        authentication_statuses: authenticationStatuses,
        workflow_checks: workflowChecks,
      }),
    );
    throw new Error("Hosted UI verification failed");
  } finally {
    await browser.close();
  }
}
main().catch(() => {
  console.error(
    "Hosted staging browser verification failed; inspect selectors, protection and scoped application configuration. No fixture credentials logged.",
  );
  process.exitCode = 1;
});
