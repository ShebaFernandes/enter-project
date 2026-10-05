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
test("FM4 search goes directly from the home composer to results", async ({
  page,
}) => {
  let reviewRequests = 0;
  await page.route("**/searches/interpret", (route) =>
    route.fulfill({
      json: {
        requires_review: false,
        ai_status: "USED",
        ambiguities: [],
        workflow_id: "00000000-0000-4000-8000-000000000002",
        criteria: {
          context: { type: "AD_HOC" },
          groups: [
            {
              id: "00000000-0000-4000-8000-000000000003",
              purpose: "REQUIREMENT",
              operator: "ALL",
            },
          ],
          criteria: [
            {
              id: "00000000-0000-4000-8000-000000000004",
              group_id: "00000000-0000-4000-8000-000000000003",
              field: "skill",
              operator: "CONTAINS",
              value: "Python",
            },
          ],
          limit: 25,
        },
      },
    }),
  );
  await page.route("**/searches", (route) =>
    route.fulfill({
      json: { search_id: "00000000-0000-4000-8000-000000000005" },
    }),
  );
  await page.route("**/search-handoffs/criteria-review", (route) => {
    reviewRequests++;
    return route.fulfill({ status: 500, json: {} });
  });
  await page.route("**/search-handoffs/search-results", (route) =>
    route.fulfill({
      status: 201,
      json: { token: "a".repeat(43) },
    }),
  );
  await page.route("**/recruiter/search/?view=results", (route) =>
    route.fulfill({ body: "Results" }),
  );
  await page.goto(fixture);
  await page.getByLabel("Describe the candidate you need").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/search\/\?view=results#handoff=/);
  expect(reviewRequests).toBe(0);
});
test("FM6 ambiguity unsafe invalid and unvalidated interpretations stay inline without execution", async ({
  page,
}) => {
  let executions = 0;
  await page.route("**/searches", (route) => {
    executions++;
    return route.fulfill({ status: 500, json: {} });
  });
  for (const response of [
    { requires_review: true, ai_status: "USED", ambiguities: ["Clarify"] },
    { requires_review: false, ai_status: "INVALID_OUTPUT", ambiguities: [] },
    { requires_review: false, ai_status: "UNAVAILABLE", ambiguities: [] },
    {
      requires_review: false,
      ai_status: "USED",
      ambiguities: ["Protected attributes rejected"],
    },
    {},
  ]) {
    await page.goto("about:blank");
    await page.route("**/searches/interpret", (route) =>
      route.fulfill({ json: { ...response, criteria: {} } }),
    );
    await page.goto(fixture);
    await page
      .getByLabel("Describe the candidate you need")
      .fill("Uncertain input");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("Clarify");
    await expect(page).toHaveURL(fixture);
  }
  expect(executions).toBe(0);
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
test("FM6 uncertain execution is not automatically or manually resubmitted", async ({
  page,
}) => {
  let executions = 0;
  await page.route("**/searches/interpret", (route) =>
    route.fulfill({
      json: {
        requires_review: false,
        ai_status: "USED",
        ambiguities: [],
        criteria: {
          context: { type: "AD_HOC" },
          groups: [{ id: "group", purpose: "REQUIREMENT", operator: "ALL" }],
          criteria: [
            {
              id: "criterion",
              group_id: "group",
              field: "skill",
              operator: "CONTAINS",
              value: "Python",
            },
          ],
          limit: 25,
        },
      },
    }),
  );
  await page.route("**/searches", (route) => {
    executions++;
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto(fixture);
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python Bengaluru");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("outcome is uncertain");
  await expect(
    page.getByRole("button", { name: "Search", exact: true }),
  ).toBeDisabled();
  expect(executions).toBe(1);
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

test("search reference controls support suggestions, reset, opening context and Enter", async ({
  page,
}) => {
  const openingId = "00000000-0000-4000-8000-000000000009";
  await page.route("**/openings", (route) =>
    route.fulfill({
      json: [{ id: openingId, title: "Backend engineer", state: "OPEN" }],
    }),
  );
  let payload:
    | { prompt: string; context: { type: string; opening_id?: string } }
    | undefined;
  await page.route("**/searches/interpret", (route) => {
    payload = route.request().postDataJSON();
    return route.fulfill({ status: 503, json: {} });
  });
  await page.goto(fixture);
  await expect(
    page
      .getByRole("navigation", { name: "Platform" })
      .getByRole("link", { name: "Results", exact: true }),
  ).toHaveAttribute("href", /view=results/);
  await expect(
    page.getByRole("link", { name: "Candidate Platform" }),
  ).toHaveAttribute("href", "/");
  await page
    .getByRole("button", { name: "Founding engineers", exact: true })
    .click();
  await expect(page.getByLabel("Describe the candidate you need")).toHaveValue(
    "Founding engineers",
  );
  await page.getByRole("button", { name: "New search", exact: true }).click();
  await expect(page.getByLabel("Describe the candidate you need")).toHaveValue(
    "",
  );
  await expect(
    page.getByLabel("Describe the candidate you need"),
  ).toBeFocused();
  await page.getByRole("button", { name: "Projects and recents" }).click();
  await page.getByLabel("Search context").selectOption(openingId);
  await page.getByRole("button", { name: "Close panel" }).click();
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python engineers");
  await page.getByLabel("Describe the candidate you need").press("Enter");
  await expect(page.getByRole("alert")).toContainText(
    "Interpretation is unavailable",
  );
  expect(payload).toEqual({
    prompt: "Python engineers",
    context: { type: "OPENING", opening_id: openingId },
  });
  await page.getByRole("button", { name: "New search", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "Projects and recents" }).click();
  await expect(page.getByLabel("Search context")).toHaveValue("");
});

for (const kind of ["recent", "saved"] as const) {
  test(`search panel restores ${kind} searches`, async ({ page }) => {
    const searchId = "00000000-0000-4000-8000-000000000005";
    await page.route(`**/${kind}-searches`, (route) =>
      route.fulfill({
        json: [
          {
            search_id: searchId,
            name: "Backend hiring",
            created_at: "2026-10-05",
          },
        ],
      }),
    );
    await page.route(`**/${kind}-searches/${searchId}`, (route) =>
      route.fulfill({ json: {} }),
    );
    await page.route("**/search-handoffs/search-results", (route) =>
      route.fulfill({ status: 201, json: { token: "a".repeat(43) } }),
    );
    await page.route("**/recruiter/search/?view=results", (route) =>
      route.fulfill({ body: "Results" }),
    );
    await page.goto(fixture);
    await page.getByRole("button", { name: "Projects and recents" }).click();
    if (kind === "saved")
      await page.getByText("Saved searches", { exact: true }).click();
    await page
      .getByRole("button", {
        name: kind === "recent" ? "Recent search 1" : "Backend hiring",
        exact: true,
      })
      .click();
    await expect(page).toHaveURL(/view=results#handoff=/);
  });
}

test("search logout reports failures and can retry successfully", async ({
  page,
}) => {
  await page.route("**/api/v1/session/sign-out", (route) =>
    route.fulfill({ status: 503, json: {} }),
  );
  await page.goto(fixture);
  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page.getByRole("alert")).toContainText("Sign-out failed");
  await page.route("**/api/v1/session/sign-out", (route) =>
    route.fulfill({ status: 204 }),
  );
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ body: "Login" }),
  );
  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/auth\/login$/);
});
