import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const fixture = "/app/tests/browser/fixtures/fm4.html";
test("FM4 speech remains editable and never automatically submits", async ({
  page,
}) => {
  let submissions = 0;
  await page.route("**/searches/interpret", (route) => {
    submissions++;
    return route.fulfill({ status: 503, json: {} });
  });
  await page.addInitScript(() => {
    class Recognition {
      onstart: (() => void) | null = null;
      onresult: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        this.onstart?.();
        this.onresult?.({ results: [[{ transcript: "Python engineers" }]] });
        this.onend?.();
      }
      stop() {
        this.onend?.();
      }
    }
    Object.defineProperty(window, "SpeechRecognition", {
      value: Recognition,
      configurable: true,
    });
  });
  await page.goto(fixture);
  await page.getByRole("button", { name: "Use speech" }).click();
  await expect(
    page.getByText("Transcript ready. Edit it, then choose Search."),
  ).toBeVisible();
  await expect(page.getByLabel("Describe the candidate you need")).toHaveValue(
    "Python engineers",
  );
  expect(submissions).toBe(0);
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Edited Python search");
  await expect(page.getByLabel("Describe the candidate you need")).toHaveValue(
    "Edited Python search",
  );
});
test("FM4 validation interpreting and degraded states are announced", async ({
  page,
}) => {
  let release!: () => void;
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/searches/interpret", async (route) => {
    await pending;
    await route.fulfill({ status: 503, json: {} });
  });
  await page.goto(fixture);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Describe the role");
  await expect(
    page.getByLabel("Describe the candidate you need"),
  ).toBeFocused();
  await page.getByLabel("Describe the candidate you need").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Interpreting the hiring need…")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Search", exact: true }),
  ).toBeDisabled();
  release();
  await expect(page.getByRole("alert")).toContainText(
    "Interpretation is unavailable",
  );
  await expect(page.getByLabel("Describe the candidate you need")).toHaveValue(
    "Python",
  );
});
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "SpeechRecognition", {
      value: undefined,
      configurable: true,
    });
    Object.defineProperty(window, "webkitSpeechRecognition", {
      value: undefined,
      configurable: true,
    });
  });
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ json: { authenticated: true } }),
  );
  for (const endpoint of ["openings", "recent-searches", "saved-searches"])
    await page.route(`**/${endpoint}`, (route) => route.fulfill({ json: [] }));
});
test("FM4 home sidebar keyboard speech fallback and visual states", async ({
  page,
}) => {
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [640, 844, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(fixture);
    await page.evaluate((value) => {
      document.documentElement.style.zoom = String(value);
    }, zoom);
    await expect(
      page.getByRole("heading", { name: "Who are we hiring today?" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Use speech" }),
    ).toBeDisabled();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page).toHaveScreenshot(`home-${width}-${zoom}.png`, {
      fullPage: true,
      animations: "disabled",
    });
    await page.getByRole("button", { name: "Projects and recents" }).click();
    await expect(
      page.getByText("No recent searches. Start with the composer."),
    ).toBeVisible();
    await expect(page).toHaveScreenshot(`sidebar-${width}-${zoom}.png`, {
      fullPage: true,
      animations: "disabled",
    });
    const axe = await new AxeBuilder({ page: page as never }).analyze();
    expect(
      axe.violations.filter((item) =>
        ["serious", "critical"].includes(item.impact ?? ""),
      ),
    ).toEqual([]);
    await page.getByRole("button", { name: "Close panel" }).focus();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Projects and recents" }),
    ).toBeFocused();
  }
});
test("FM4 rate limit and sidebar errors retain typed input without storage", async ({
  page,
}) => {
  await page.route("**/recent-searches", (route) =>
    route.fulfill({ status: 503, json: {} }),
  );
  await page.route("**/searches/interpret", (route) =>
    route.fulfill({ status: 429, json: {} }),
  );
  await page.goto(fixture);
  await page.getByRole("button", { name: "Projects and recents" }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await page.getByRole("button", { name: "Close panel" }).click();
  await page.getByLabel("Describe the candidate you need").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Too many requests");
  await expect(page.getByLabel("Describe the candidate you need")).toHaveValue(
    "Python",
  );
  expect(
    await page.evaluate(() => ({
      local: { ...localStorage },
      session: { ...sessionStorage },
    })),
  ).toEqual({ local: {}, session: {} });
});
