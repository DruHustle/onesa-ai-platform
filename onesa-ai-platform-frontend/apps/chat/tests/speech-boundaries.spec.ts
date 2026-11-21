import {test, expect} from "@playwright/test";

test("speech recording and playback controls are absent before sign-in", async ({page}) => {
  await page.goto("/");
  await expect(page.getByRole("button", {name: "Dictate message"})).toHaveCount(0);
  await expect(page.getByRole("button", {name: "Listen to AI response"})).toHaveCount(0);
});
