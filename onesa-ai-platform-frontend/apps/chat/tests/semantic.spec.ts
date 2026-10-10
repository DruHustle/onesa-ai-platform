import { test, expect } from "@playwright/test";

test("real semantic document search and source-grounded native chat", async ({
  page,
}, info) => {
  test.skip(
    process.env.ONESA_SEMANTIC_BROWSER !== "1",
    "Explicit isolated real embedding/native-chat service required",
  );
  test.setTimeout(90000);
  await page.goto("/");
  await page
    .getByRole("button", { name: "New to Onesa? Create an account" })
    .click();
  await page.getByLabel("Display name").fill("Semantic Browser Tester");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`semantic-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("semantic-browser-password-123!");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "＋ New conversation" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Knowledge", exact: true }).click();
  const passage =
    "Wenn die Temperatur eines Akkupacks über den sicheren Betriebsbereich steigt, wird das Laden unterbrochen. Ein Techniker prüft die Kühlung und den Zustand der Zellen.";
  await page
    .getByLabel("Document (.txt or .pdf, up to 5 MiB)")
    .setInputFiles({
      name: "synthetic-battery-guide.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(passage),
    });
  await page
    .getByRole("button", { name: "Upload document", exact: true })
    .click();
  await expect(
    page.getByText("Configured embedding model", { exact: true }),
  ).toBeVisible({ timeout: 30000 });
  await page
    .getByLabel("Search your documents")
    .fill("What should happen if a battery gets too hot during charging?");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByText("synthetic-battery-guide.txt · excerpt 1", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(passage, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Ask about this document →" }).click();
  await expect(page.getByText("Use documents (1 selected)", { exact: true })).toBeVisible();
  await page
    .getByLabel("Message Onesa AI")
    .fill(
      "Based only on the uploaded passage, what must happen when a battery overheats while charging? Reply in English in one sentence.",
    );
  await page.getByLabel("Send message").click();
  await expect(page.locator(".sources")).toContainText(
    "synthetic-battery-guide.txt",
    { timeout: 30000 },
  );
  await expect(page.locator(".message.assistant")).toContainText(/charg/i);
  await expect(page.locator(".message.assistant")).toContainText(
    /stop|interrupt|halt|discontinu|suspend|ceas/i,
  );
  await page.reload();
  await page
    .getByRole("button", { name: /Based only on the uploaded passage/ })
    .click();
  await expect(page.locator(".sources")).toContainText(
    "synthetic-battery-guide.txt",
    { timeout: 30000 },
  );
  await page.screenshot({
    path: info.outputPath("semantic-grounded-chat.png"),
    fullPage: true,
  });
});
