import { expect, test } from "@playwright/test";

test("the product overview requires no workspace API and opens the chosen feature", async ({ page }) => {
  const initialApiCalls: string[] = [];
  const collectApi = (url: string) => {
    const path = new URL(url).pathname;
    if (path.startsWith("/api/")) initialApiCalls.push(path);
  };
  await page.route("**/api/**", route => {
    collectApi(route.request().url());
    return route.abort();
  });
  await page.goto("/explore");
  await expect(page.getByRole("heading", { name: "Onesa AI Platform" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Create account" })).toHaveAttribute(
    "href", "https://account.onesa.eu/register?product=ai&platform=web&audience=user",
  );
  await page.getByText("Synthetic example", { exact: true }).first().click();
  await expect(page.getByText("A draft agenda turns three project updates into discussion topics.")).toBeVisible();
  await page.getByLabel("Interface language").selectOption("de");
  await expect(page.getByRole("heading", { name: "Funktionen" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Chat öffnen" })).toHaveAttribute("href", "/?sign-in=1");
  expect(initialApiCalls).toEqual([]);
  await page.unroute("**/api/**");
  await page.getByRole("link", { name: "Wissen öffnen" }).click();
  await expect(page).toHaveURL(/\/knowledge$/);
});
