import { test, expect } from "@playwright/test";

test("real local model streams, remembers context and persists", async ({
  page,
}) => {
  test.skip(
    process.env.ONESA_REAL_INFERENCE !== "1",
    "Explicit real inference acceptance only",
  );
  test.setTimeout(120_000);
  await page.goto("/");
  await page
    .getByRole("button", { name: "New to Onesa? Create an account" })
    .click();
  await page.getByLabel("Display name").fill("Real Inference Tester");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`real-browser-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("real-browser-password-123!");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByText(/Real inference/)).toBeVisible();
  await page
    .getByLabel("Message Onesa AI")
    .fill(
      "Remember the project codename MAPLE-829. Reply with a short acknowledgment.",
    );
  await page.getByLabel("Send message").click();
  await expect(page.locator("article.message.assistant")).toHaveCount(1, {
    timeout: 60_000,
  });
  await page
    .getByLabel("Message Onesa AI")
    .fill("What is the project codename? Reply with only the codename.");
  await page.getByLabel("Send message").click();
  await expect(page.locator("article.message.assistant")).toHaveCount(2, {
    timeout: 60_000,
  });
  await expect(page.locator("article.message.assistant").last()).toContainText(
    "MAPLE-829",
  );
  await expect(page.getByText(/\[Mock response/)).toHaveCount(0);
  await page.reload();
  await page
    .getByRole("button", { name: /Remember the project codename/ })
    .click();
  await expect(page.locator("article.message.assistant")).toHaveCount(2);
  await expect(page.locator("article.message.assistant").last()).toContainText(
    "MAPLE-829",
  );
  await page.screenshot({
    path: "../../../data/screenshots/chat-real-local.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "＋ New conversation" }).click();
  await page
    .getByLabel("Message Onesa AI")
    .fill("Write a long numbered list of 500 household items.");
  await page.getByLabel("Send message").click();
  const live = page.locator("article.message").filter({
    hasText: "Onesa AI · Generating",
  });
  await expect(live.locator("p, li").first()).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole("button", { name: "Stop", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(
    page.getByText("Generation stopped.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page
    .getByRole("button", { name: /Write a long numbered list/ })
    .click();
  await expect(page.locator("article.message.assistant")).toHaveCount(0);
  await page.getByLabel("Message Onesa AI").fill("Reply with READY only.");
  await page.getByLabel("Send message").click();
  await expect(page.locator("article.message.assistant")).toContainText(
    "READY",
    {
      timeout: 60_000,
    },
  );
});
