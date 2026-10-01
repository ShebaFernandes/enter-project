import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const tenantId = "00000000-0000-4000-8000-000000000001";
const searchId = "00000000-0000-4000-8000-000000000002";
const firstId = "00000000-0000-4000-8000-000000000003";
const secondId = "00000000-0000-4000-8000-000000000004";
const contextToken = "c".repeat(43);

test.beforeEach(async ({ page }) => {
  let selected = [firstId, secondId];
  let version = 1;
  await page.route("**/search-handoffs/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    if (path.endsWith("/display"))
      return route.fulfill({ json: searchResponse });
    if (path.endsWith("/return"))
      return route.fulfill({
        json: {
          return_path: `/search-page?view=results#handoff=${"r".repeat(43)}&selection=${contextToken}`,
        },
      });
    if (method === "POST") {
      if (path.endsWith("comparison-selection"))
        selected = route.request().postDataJSON().candidate_ids;
      return route.fulfill({
        status: 201,
        json: {
          token: path.endsWith("comparison-selection")
            ? contextToken
            : "r".repeat(43),
        },
      });
    }
    if (method === "PATCH") {
      selected = route.request().postDataJSON().candidate_ids;
      version += 1;
    }
    return route.fulfill({
      json: {
        search_id: searchId,
        candidate_ids: selected,
        etag: `"v${version}"`,
      },
    });
  });
});

const searchShell = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Search</title><link rel="stylesheet" href="/app/static/dist/assets/app.css"></head><body><main><div data-recruiter-search data-tenant-id="${tenantId}"><h1>Find candidates</h1><form data-search-form><input type="hidden" name="csrfmiddlewaretoken" value="synthetic"><label>Describe the candidate you need<textarea name="prompt"></textarea></label><button type="button" data-speech>Use speech</button><button type="submit">Search</button><p data-speech-status role="status"></p><label>Context<select name="context"><option>AD_HOC</option></select></label><label data-opening-row hidden>Opening<input name="opening_id"></label><div data-criteria-list></div><button type="button" data-add-criterion>Add criterion</button></form><button data-toggle-criteria aria-expanded="true">Criteria</button><aside data-criteria-panel></aside><div class="search-status" role="status"></div><nav aria-label="Result filters"><button data-filter="all" aria-pressed="true">All</button></nav><section><div data-comparison-toolbar><p data-comparison-count role="status">0 candidates selected for comparison.</p><button type="button" data-open-comparison aria-disabled="true">Compare selected candidates</button></div><div data-results tabindex="-1"></div><button data-more hidden>Load more</button></section><dialog data-candidate-dialog aria-labelledby="candidate-title"><h2 id="candidate-title">Candidate</h2><div data-detail></div><button data-close-detail>Close</button></dialog></div></main><script type="module" src="/app/static/dist/assets/app.js"></script></body></html>`;

const comparisonShell = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Compare candidates</title><link rel="stylesheet" href="/app/static/dist/assets/app.css"></head><body><main><div class="comparison-shell" data-comparison data-tenant-id="${tenantId}"><header><p class="eyebrow">Recruiter workspace</p><h1>Compare candidates</h1><button type="button" data-close-comparison>Return to results</button></header><p data-comparison-status role="status" aria-live="polite"></p><section data-comparison-empty><h2>No candidates selected</h2><p>Select between two and ten candidates from the current authorized result view.</p></section><section data-comparison-content hidden aria-labelledby="comparison-heading"><h2 id="comparison-heading">Side-by-side evidence</h2><div data-comparison-candidates></div></section></div></main><script type="module" src="/app/static/dist/assets/app.js"></script></body></html>`;

const searchResponse = {
  search_id: searchId,
  next_cursor: null,
  items: [firstId, secondId].map((candidateId, index) => ({
    candidate_id: candidateId,
    summary: {
      name: `Synthetic Candidate ${index + 1}`,
      current_role: "Engineer",
      location: { display: "Bengaluru" },
    },
    evidence: [{ field: "skill" }],
    unknowns: [],
    findings: [],
  })),
};

const field = (state: "KNOWN" | "UNKNOWN" | "UNAVAILABLE", value: unknown) => ({
  state,
  value,
  provenance: state === "KNOWN" ? ["CANDIDATE_REPORTED"] : [],
});

const comparisonResponse = {
  fields: [
    "name",
    "location",
    "experience",
    "notice_or_availability",
    "compensation_availability",
    "skills",
    "employment",
    "preferences",
    "match_evidence",
    "informational_findings",
  ],
  candidates: [
    {
      candidate_id: firstId,
      permitted_fields: {
        name: field("KNOWN", "Synthetic Candidate 1"),
        location: field("KNOWN", "Bengaluru"),
        experience: field("KNOWN", "5.00 years"),
        notice_or_availability: field("KNOWN", "30 days"),
        compensation_availability: field("UNAVAILABLE", null),
        skills: field("KNOWN", ["Python"]),
        employment: field("KNOWN", ["Engineer — Synthetic Employer"]),
        preferences: field("KNOWN", ["Remote"]),
        match_evidence: field("KNOWN", ["skill"]),
        informational_findings: field("KNOWN", ["SHORT_TENURE"]),
      },
      evidence: [],
      findings: [
        {
          code: "SHORT_TENURE",
          informational_only: true,
          message:
            "Candidate left Synthetic Employer after approximately 8 months.",
          evidence: {},
        },
      ],
      unknowns: ["compensation_availability"],
    },
    {
      candidate_id: secondId,
      permitted_fields: Object.fromEntries(
        [
          "name",
          "location",
          "experience",
          "notice_or_availability",
          "compensation_availability",
          "skills",
          "employment",
          "preferences",
          "match_evidence",
          "informational_findings",
        ].map((name) => [
          name,
          field(
            name === "name" ? "KNOWN" : "UNKNOWN",
            name === "name" ? "Synthetic Candidate 2" : null,
          ),
        ]),
      ),
      evidence: [],
      findings: [],
      unknowns: ["employment", "skills"],
    },
  ],
};

test("selects, compares, removes, preserves state, and returns focus accessibly", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.route("**/tenants/*/recruiter/comparison/", (route) =>
    route.fulfill({ contentType: "text/html", body: comparisonShell }),
  );
  await page.route("**/search-page", (route) =>
    route.fulfill({ contentType: "text/html", body: searchShell }),
  );
  await page.route(/\/searches$/, (route) =>
    route.fulfill({ json: searchResponse }),
  );
  await page.route("**/comparisons", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(comparisonResponse),
    }),
  );
  await page.goto("/search-page");
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python engineers");
  await page.getByLabel("Value").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByLabel("Compare Synthetic Candidate 1").check();
  await page.getByLabel("Compare Synthetic Candidate 2").check();
  await expect(
    page.getByText("2 candidates selected for comparison."),
  ).toBeVisible();
  const compareButton = page.getByRole("button", {
    name: "Compare selected candidates",
  });
  await compareButton.click();
  await expect(page).toHaveURL(/\/recruiter\/comparison\/#handoff=/);
  await expect(
    page.getByRole("heading", { name: "Side-by-side evidence" }),
  ).toBeVisible();
  await expect(
    page.getByText("Unknown", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Unavailable", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/SHORT_TENURE is informational only/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Remove Synthetic Candidate 1" })
    .click();
  await expect(page.getByText("Synthetic Candidate 1")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Remove Synthetic Candidate 2" }),
  ).toBeFocused();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 640, height: 800 });
  await page.evaluate(() => {
    document.documentElement.style.zoom = "200%";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const results = await new AxeBuilder({ page: page as never }).analyze();
  expect(
    results.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("returns focus to the comparison invoker", async ({ page }) => {
  await page.route("**/search-page", (route) =>
    route.fulfill({ contentType: "text/html", body: searchShell }),
  );
  await page.goto("/search-page");
  await page.evaluate(() => {
    history.replaceState(null, "", "?view=results");
    window.dispatchEvent(new PageTransitionEvent("pageshow"));
  });
  await expect(
    page.getByRole("button", { name: "Compare selected candidates" }),
  ).toBeFocused();
});

test("shows empty guidance and removes stale unauthorized selections", async ({
  page,
}) => {
  await page.route("**/comparison-page", (route) =>
    route.fulfill({ contentType: "text/html", body: comparisonShell }),
  );
  await page.goto("/comparison-page");
  await expect(
    page.getByRole("heading", { name: "No candidates selected" }),
  ).toBeVisible();

  await page.evaluate(
    (token) => history.replaceState(null, "", `#handoff=${token}`),
    contextToken,
  );
  await page.route("**/comparisons", (route) =>
    route.fulfill({
      json: {
        ...comparisonResponse,
        candidates: [comparisonResponse.candidates[0]],
      },
    }),
  );
  await page.reload();
  await expect(page.getByRole("status")).toContainText(
    "1 selected candidate is no longer available",
  );
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("enter.comparison-selection.v1"),
    ),
  ).toBeNull();
});
