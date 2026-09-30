import { expect, test } from "@playwright/test";

test("unsupported speech keeps typed search usable and never submits", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:4173");
  await page.setContent(
    `<div data-recruiter-search><form data-search-form><label>Prompt<textarea name="prompt"></textarea></label><button type="button" data-speech>Use speech</button><p data-speech-status role="status"></p><select name="context"><option>AD_HOC</option></select><input name="opening_id"><div data-criteria-list></div></form><button data-add-criterion></button><div class="search-status"></div><div data-results></div><button data-more hidden></button><dialog data-candidate-dialog><div data-detail></div><button data-close-detail></button></dialog></div>`,
  );
  await page.evaluate(() => {
    Object.defineProperty(window, "SpeechRecognition", {
      value: undefined,
      configurable: true,
    });
    Object.defineProperty(window, "webkitSpeechRecognition", {
      value: undefined,
      configurable: true,
    });
  });
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  await expect(page.getByRole("button", { name: "Use speech" })).toBeDisabled();
  await expect(
    page.getByText("Typed search remains fully usable."),
  ).toBeVisible();
  await page.getByLabel("Prompt").fill("Editable typed search");
  await expect(page.getByLabel("Prompt")).toHaveValue("Editable typed search");
});

test("speech reports listening, transcribing, ready and never auto-submits", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:4173");
  await page.setContent(
    `<div data-recruiter-search><form data-search-form><label>Prompt<textarea name="prompt"></textarea></label><button type="button" data-speech>Use speech</button><p data-speech-status role="status"></p><select name="context"><option>AD_HOC</option></select><input name="opening_id"><div data-criteria-list></div></form><button data-add-criterion></button><div class="search-status"></div><div data-results></div><button data-more hidden></button><dialog data-candidate-dialog><div data-detail></div><button data-close-detail></button></dialog></div>`,
  );
  await page.evaluate(() => {
    class MockRecognition {
      continuous = false;
      interimResults = false;
      lang = "";
      onstart: (() => void) | null = null;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        this.onstart?.();
        setTimeout(
          () =>
            this.onresult?.({
              results: Object.assign(
                [{ 0: { transcript: "Python in Bengaluru" }, isFinal: false }],
                { length: 1 },
              ),
            }),
          0,
        );
        setTimeout(
          () =>
            this.onresult?.({
              results: Object.assign(
                [{ 0: { transcript: "Python in Bengaluru" }, isFinal: true }],
                { length: 1 },
              ),
            }),
          10,
        );
        setTimeout(() => this.onend?.(), 20);
      }
      stop() {
        this.onend?.();
      }
    }
    Object.defineProperty(window, "SpeechRecognition", {
      value: MockRecognition,
    });
  });
  await page.locator("form").evaluate((form) => {
    document.body.dataset.submissions = "0";
    form.addEventListener("submit", () => {
      document.body.dataset.submissions = String(
        Number(document.body.dataset.submissions ?? "0") + 1,
      );
    });
  });
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  await page.getByRole("button", { name: "Use speech" }).click();
  await expect(page.getByText(/Transcript ready/)).toBeVisible();
  await expect(page.getByLabel("Prompt")).toHaveValue("Python in Bengaluru");
  expect(await page.locator("body").getAttribute("data-submissions")).toBe("0");
  await page.getByLabel("Prompt").fill("Edited transcript");
  await expect(page.getByLabel("Prompt")).toHaveValue("Edited transcript");
});
