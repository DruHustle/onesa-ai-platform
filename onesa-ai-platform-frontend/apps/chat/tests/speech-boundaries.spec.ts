import {test, expect} from "@playwright/test";

test("speech recording and playback controls are absent before sign-in", async ({page}) => {
  await page.goto("/");
  await expect(page.getByRole("button", {name: "Dictate message"})).toHaveCount(0);
  await expect(page.getByRole("button", {name: "Listen to AI response"})).toHaveCount(0);
});

test("mocked microphone produces an editable draft and playback requires a click", async ({page}) => {
  // Browser API simulation, not evidence of audible or provider-level speech accuracy.
  await page.addInitScript(() => {
    class Recognition {
      lang = "en-US"; continuous = false; interimResults = false; maxAlternatives = 1;
      onresult: ((event: {resultIndex: number; results: {isFinal: boolean; 0: {transcript: string}}[]}) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        setTimeout(() => {
          this.onresult?.({resultIndex: 0, results: [{isFinal: true, 0: {transcript: "Hello by voice"}}]});
          this.onend?.();
        }, 10);
      }
      stop() {this.onend?.();}
      abort() {this.onend?.();}
    }
    class Utterance {
      text: string; lang = ""; rate = 1; onstart: (() => void) | null = null;
      constructor(text: string) {this.text = text;}
    }
    const engine = {
      speak(value: Utterance) {sessionStorage.setItem("voice-test-spoken", value.text); value.onstart?.();},
      pause() {}, resume() {}, cancel() {}, getVoices() {return [];},
      addEventListener() {}, removeEventListener() {},
    };
    Object.defineProperty(window, "SpeechRecognition", {configurable: true, value: Recognition});
    Object.defineProperty(window, "SpeechSynthesisUtterance", {configurable: true, value: Utterance});
    Object.defineProperty(window, "speechSynthesis", {configurable: true, value: engine});
  });
  await page.goto("/");
  await page.getByRole("button", {name: "New to Onesa? Create an account"}).click();
  await page.getByLabel("Display name").fill("Voice Tester");
  await page.getByLabel("Email", {exact: true}).fill(`speech-${Date.now()}@example.com`);
  await page.getByLabel("Password", {exact: true}).fill("browser-voice-fixture-password-2026");
  await page.getByRole("button", {name: "Create account", exact: true}).click();
  await page.getByRole("button", {name: "Dictate message"}).click();
  await expect(page.getByLabel("Message Onesa AI")).toHaveValue("Hello by voice");
  // A textarea's editable value is text too; only submitted messages count.
  await expect(page.locator(".messages article.message").filter({hasText:"Hello by voice"})).toHaveCount(0);
  await page.getByLabel("Message Onesa AI").fill("Edited speech question");
  await page.getByRole("button", {name: "Send message"}).click();
  await expect(page.getByText("[Mock response — no AI inference] Edited speech question")).toBeVisible();
  await page.getByRole("button", {name: "Listen to AI response"}).click();
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("voice-test-spoken")))
    .toContain("Edited speech question");
  await page.getByRole("button", {name: "Pause speech"}).click();
  await page.getByRole("button", {name: "Resume speech"}).click();
  await page.getByRole("button", {name: "Stop speech"}).click();
});
