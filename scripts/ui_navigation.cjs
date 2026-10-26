// Readiness of the actual owned interface, independent of optional navigation IO.
const routes = {
  "/": {
    label: "Message Onesa AI",
    api: ["auth/me", "models", "conversations", "knowledge/documents"],
  },
  "/knowledge": { label: "Search your documents", api: ["auth/me", "knowledge/documents"] },
  "/agents": { label: "Text to analyze", api: ["auth/me", "agents/runs"] },
  "/travel": { label: "Destination", api: ["auth/me", "travel/trips"] },
  "/settings": { label: "Display name", api: ["auth/me", "auth/sessions"] },
  "/recovery": { heading: "Account recovery", api: [] },
  "/invitation": { heading: "Accept invitation", api: [] },
};

async function navigateInterface(
  page, origin, route = "/", { authentication = false, timeout = 30000 } = {},
) {
  const target = new URL(route, origin);
  if (!Object.hasOwn(routes, route) || target.origin !== new URL(origin).origin)
    throw Error("Unsupported interface route");
  const profile = routes[route];
  const waits = (authentication ? [] : profile.api).map((path) =>
    page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.origin === target.origin && url.pathname === "/api/v1/" + path;
    }, { timeout }).then(async (response) => {
      if (response.status() !== 200 || await response.finished())
        throw Error("Required interface data response failed");
    }),
  );
  // Handle failures immediately even when document navigation fails. Awaiting
  // this same promise below still fails closed on any required response failure.
  const dataReady = Promise.all(waits);
  dataReady.catch(() => {});
  const response = await page.goto(target.href, { waitUntil: "domcontentloaded", timeout });
  if (!response || response.status() !== 200) throw Error("Interface route failed");
  const landed = new URL(response.url());
  if (landed.origin !== target.origin || landed.pathname !== target.pathname)
    throw Error("Interface route changed");
  const content = authentication
    ? page.getByLabel("Email", { exact: true })
    : profile.label
      ? page.getByLabel(profile.label, { exact: true })
      : page.getByRole("heading", { name: profile.heading, exact: true, level: 1 });
  await Promise.all([content.waitFor({ state: "visible", timeout }), dataReady]);
  return response;
}

module.exports = { navigateInterface };
