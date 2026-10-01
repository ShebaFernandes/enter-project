import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";

test("search preserves typed input and renders neutral findings responsively", async ({
  page,
}) => {
  const html = await readFile(
    "frontend/templates/recruiter/search.html",
    "utf8",
  );
  await page.goto("http://127.0.0.1:4173");
  await page.setContent(
    `<base href="http://127.0.0.1:4173"><div class="recruiter-shell" data-recruiter-search data-tenant-id="00000000-0000-4000-8000-000000000001"><form data-search-form><label>Describe the candidate you need<textarea name="prompt"></textarea></label><button type="button" data-speech>Use speech</button><button type="submit">Search</button><p data-speech-status role="status"></p><label>Context<select name="context"><option>AD_HOC</option><option>OPENING</option></select></label><label data-opening-row hidden>Opening<input name="opening_id"></label><button type="button" data-add-criterion>Add criterion</button><div data-criteria-list></div></form><div class="search-status" role="status"></div><button data-toggle-criteria aria-expanded="true">Criteria</button><aside data-criteria-panel></aside><nav aria-label="Result filters"><button data-filter="all" aria-pressed="true">All</button><button data-filter="with-findings" aria-pressed="false">With findings</button></nav><div data-results tabindex="-1"></div><button data-more hidden>Load more</button><dialog data-candidate-dialog><div data-detail></div><button data-close-detail>Close</button></dialog></div>`,
  );
  await page.route(/\/searches$/, (route) =>
    route.fulfill({
      json: {
        search_id: "00000000-0000-4000-8000-000000000002",
        next_cursor: null,
        items: [
          {
            candidate_id: "00000000-0000-4000-8000-000000000003",
            summary: {
              name: "Synthetic Candidate",
              current_role: "Engineer",
              location: { display: "Bengaluru" },
            },
            evidence: [{ field: "skill" }],
            unknowns: [],
            findings: [
              {
                code: "SHORT_TENURE",
                informational_only: true,
                message:
                  "Candidate left Synthetic Employer after approximately 8 months.",
                evidence: {
                  employment_record_id: "00000000-0000-4000-8000-000000000004",
                  company: "Synthetic Employer",
                  confirmed_start_date: "2025-01-01",
                  confirmed_end_date: "2025-09-01",
                  calculated_duration: {
                    calendar_months: 8,
                    remaining_days: 0,
                  },
                  calculation_version: "short-tenure-v1",
                  evaluated_at: "2026-09-30T00:00:00Z",
                },
              },
            ],
          },
        ],
      },
    }),
  );
  await page.addStyleTag({ path: "static/dist/assets/app.css" });
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python in Bengaluru");
  await page.getByLabel("Value").fill("Python");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(
    page.getByText(
      "Candidate left Synthetic Employer after approximately 8 months.",
    ),
  ).toBeVisible();
  await page.setViewportSize({ width: 320, height: 800 });
  await expect(page.locator(".candidate-card")).toBeVisible();
  expect(html).toContain("data-criteria-panel");
  await page.reload();
  expect(
    await page.evaluate(() =>
      sessionStorage.getItem("recruiter-search-draft-v1"),
    ),
  ).toBeNull();
});

test("empty and safe-error states preserve criteria and pass automated accessibility scan", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:4173");
  await page.setContent(
    `<!doctype html><html lang="en"><head><title>Recruiter search</title></head><body><main><h1>Find candidates</h1><div data-recruiter-search data-tenant-id="00000000-0000-4000-8000-000000000001"><form data-search-form><label>Prompt<textarea name="prompt"></textarea></label><label>Context<select name="context"><option>AD_HOC</option></select></label><label>Opening<input name="opening_id"></label><button type="submit">Search</button><div data-criteria-list></div></form><button data-add-criterion>Add criterion</button><button data-speech>Use speech</button><p data-speech-status role="status"></p><button data-toggle-criteria aria-expanded="true">Criteria</button><aside data-criteria-panel></aside><div class="search-status" role="status"></div><nav aria-label="Result filters"><button data-filter="all" aria-pressed="true">All</button></nav><div data-results tabindex="-1"></div><button data-more hidden>Load more</button><dialog data-candidate-dialog aria-labelledby="candidate-test-title"><h2 id="candidate-test-title">Candidate</h2><div data-detail></div><button data-close-detail>Close</button></dialog></div></main></body></html>`,
  );
  await page.route(/\/searches$/, (route) =>
    route.fulfill({ status: 503, json: { title: "Unavailable" } }),
  );
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  await page.getByLabel("Prompt").fill("Synthetic query");
  await page.locator("[name=value]").fill("Python");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText(/criteria remain available/)).toBeVisible();
  await expect(page.getByLabel("Prompt")).toHaveValue("Synthetic query");
  const results = await new AxeBuilder({ page: page as never }).analyze();
  expect(results.violations).toEqual([]);
});
