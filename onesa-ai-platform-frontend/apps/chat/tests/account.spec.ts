import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

// Register the existing account journey budget before browser/page fixture setup.
test.describe.configure({ timeout: 90000 });

test("account profile, session revocation, password rotation and responsive accessibility", async ({
  page,
  browser,
  baseURL,
}, info) => {
  const email = `account-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
  const password = "browser-account-password-123!",
    newPassword = "browser-account-changed-456!";
  await page.goto("/");
  await page
    .getByRole("button", { name: "New to Onesa? Create an account" })
    .click();
  await page.getByLabel("Display name").fill("Account Tester");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "＋ New conversation" }),
  ).toBeVisible();
  const other = await browser.newContext({ baseURL });
  try {
    expect(
      (
        await other.request.post("/api/v1/auth/login", {
          headers: { Origin: new URL(baseURL!).origin },
          data: { email, password },
        })
      ).status(),
    ).toBe(200);
    await page
      .getByRole("link", { name: "Account settings", exact: true })
      .click();
    await page
      .getByLabel("Display name", { exact: true })
      .fill("Updated Tester");
    await page.getByRole("button", { name: "Save display name" }).click();
    await expect(page.getByRole("status")).toHaveText("Display name saved.");
    await page.reload();
    await expect(page.getByLabel("Display name", { exact: true })).toHaveValue(
      "Updated Tester",
    );
    await expect(page.getByText(/2 active sessions/)).toBeVisible();
    await page.getByLabel("Password to sign out other sessions").fill(password);
    await page
      .getByRole("button", { name: "Sign out other sessions", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText(
      "Other sessions signed out",
    );
    expect((await other.request.get("/api/v1/auth/me")).status()).toBe(401);
    await expect(
      page.getByLabel("Password to sign out other sessions"),
    ).toHaveValue("");
    for (const width of [320, 390, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(null)))));
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page.screenshot({
        path: info.outputPath(`settings-${width}.png`),
        fullPage: true,
      });
    }
    await page.getByLabel("Current password", { exact: true }).fill(password);
    await page.getByLabel("New password", { exact: true }).fill(newPassword);
    await page
      .getByLabel("Confirm new password", { exact: true })
      .fill(newPassword);
    await page
      .getByRole("button", { name: "Change password", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("Password changed");
    await expect(
      page.getByLabel("Current password", { exact: true }),
    ).toHaveValue("");
    await page.getByRole("link", { name: "Chat", exact: true }).click();
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await page.getByLabel("Email", { exact: true }).fill(email);
    await page.getByLabel("Password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.locator(".error[role=alert]")).toContainText(
      "Invalid email or password",
    );
    await page.getByLabel("Password", { exact: true }).fill(newPassword);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "＋ New conversation" }),
    ).toBeVisible();
    await page
      .getByRole("link", { name: "Account settings", exact: true })
      .click();
    await page.getByLabel("Password to export your data").fill(newPassword);
    const downloading = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download account export" }).click();
    const download = await downloading;
    expect(download.suggestedFilename()).toBe("onesa-account-export.json");
    const exported = JSON.parse(
      await readFile((await download.path())!, "utf8"),
    );
    expect(exported.account.email).toBe(email);
    expect(exported.account.display_name).toBe("Updated Tester");
    await expect(page.getByLabel("Password to export your data")).toHaveValue(
      "",
    );
    await page.getByLabel("Password to delete your account").fill(newPassword);
    await page
      .getByLabel("Type DELETE MY ACCOUNT to confirm")
      .fill("DELETE MY ACCOUNT");
    await page
      .getByRole("button", { name: "Delete my account permanently" })
      .click();
    await expect(page.getByRole("status")).toContainText(
      "live application data were deleted",
    );
    expect((await page.request.get("/api/v1/auth/me")).status()).toBe(401);
  } finally {
    await other.close();
  }
});
