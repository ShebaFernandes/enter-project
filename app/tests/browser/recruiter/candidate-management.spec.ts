import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const shell = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Candidate management</title><link rel="stylesheet" href="/app/static/dist/assets/app.css"></head><body><main><div data-candidate-management data-tenant-id="11111111-1111-4111-8111-111111111111" data-candidate-id="22222222-2222-4222-8222-222222222222"><h1>Candidate details</h1><input type="hidden" name="csrfmiddlewaretoken" value="synthetic"><p data-page-status role="status"></p><section><h2>Overview</h2><p data-candidate-summary></p></section><aside data-conflict tabindex="-1" role="alert" hidden></aside><div class="management-grid"><section><h2>Private recruiter notes</h2><ul data-notes></ul><form data-note-form data-dirty="false"><label for="note">New private note</label><textarea id="note" name="body" required></textarea><button>Save private note</button></form></section><section><h2>Internal workflow</h2><form data-work-form data-dirty="false"><label for="status">Internal status</label><select id="status" name="internal_status"><option>SOURCED</option><option>SHORTLISTED</option><option>NOT_RELEVANT</option></select><label><input type="checkbox" name="shortlisted"> Add to shortlist</label><label for="reason">Reason</label><input id="reason" name="structured_reason"><button>Save internal workflow</button></form></section><section><h2>Candidate-facing status</h2><form data-publication-form><label for="publication">Status to preview</label><select id="publication" name="publication_internal_status"><option>SHORTLISTED</option></select><button>Preview candidate-facing status</button><div data-status-preview hidden></div><label for="candidate-status">Candidate-facing status</label><select id="candidate-status" name="candidate_status"><option>SHORTLISTED</option></select><button type="button" data-publish-status hidden>Confirm and publish status</button></form></section><section><h2>Contact or share</h2><form data-disclosure-form><label for="purpose">Purpose</label><select id="purpose" name="purpose"><option>HIRING_TEAM_SHARE</option></select><label for="destination-type">Destination type</label><select id="destination-type" name="destination_type"><option>HIRING_TEAM</option></select><label for="destination">Destination</label><input id="destination" name="destination_identifier" value="team-1"><label for="destination-label">Destination label</label><input id="destination-label" name="destination_label" value="Synthetic panel"><label><input type="checkbox" name="fields" value="name" checked> Name</label><button>Preview minimum disclosure</button></form><div data-disclosure-preview hidden></div><button type="button" data-confirm-disclosure hidden>Confirm disclosure</button><p data-disclosure-status role="status"></p></section></div></div></main><script type="module" src="/app/static/dist/assets/app.js"></script></body></html>`;

test("candidate management is keyboard operable, conflict-safe, and minimum-disclosure aware", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.route("**/candidate-management?search_id=s1", (route) =>
    route.fulfill({ contentType: "text/html", body: shell }),
  );
  await page.route("**/api/v1/tenants/*/candidates/*?search_id=s1", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        candidate_id: "22222222-2222-4222-8222-222222222222",
        permitted_fields: {
          name: "Synthetic Candidate",
          current_role: "Engineer",
        },
        evidence: [{}],
        findings: [],
        unknowns: [],
        candidate_work: {
          id: "33333333-3333-4333-8333-333333333333",
          version: 1,
          internal_status: "SOURCED",
          shortlisted: false,
        },
        application_context: null,
      }),
    }),
  );
  await page.route(
    "**/candidate-work/33333333-3333-4333-8333-333333333333",
    async (route) => {
      if (route.request().method() === "PATCH") {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            current: { internal_status: "CONTACTED", shortlisted: false },
            attempted: { internal_status: "SHORTLISTED", shortlisted: true },
            changed_fields: ["internal_status", "shortlisted"],
            current_etag: '"fresh"',
          }),
        });
        return;
      }
      await route.fulfill({
        headers: { ETag: '"initial"' },
        contentType: "application/json",
        body: JSON.stringify({
          internal_status: "SOURCED",
          shortlisted: false,
        }),
      });
    },
  );
  await page.route("**/candidate-work/*/notes", (route) =>
    route.fulfill({
      status: route.request().method() === "POST" ? 201 : 200,
      contentType: "application/json",
      body: route.request().method() === "POST" ? "{}" : "[]",
    }),
  );
  await page.route("**/disclosures/preview", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        preview_id: "44444444-4444-4444-8444-444444444444",
        preview_hash: "a".repeat(64),
        destination: { type: "HIRING_TEAM", label: "Synthetic panel" },
        purpose: "HIRING_TEAM_SHARE",
        permitted_fields: ["name"],
        excluded_fields: [],
        expires_at: new Date(Date.now() + 60_000).toISOString(),
        state: "PREVIEWED",
      }),
    }),
  );
  await page.goto("/candidate-management?search_id=s1");
  await expect(page.getByText("Candidate context loaded.")).toBeVisible();
  await page.getByLabel("New private note").fill("Synthetic private note");
  await page.getByRole("button", { name: "Save private note" }).click();
  await expect(page.getByText(/Private note saved/)).toBeVisible();
  await page.getByLabel("Internal status").selectOption("SHORTLISTED");
  await page.getByLabel("Add to shortlist").check();
  await page.getByRole("button", { name: "Save internal workflow" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Nothing was overwritten",
  );
  await page.getByRole("button", { name: "Use stored version" }).click();
  await page
    .getByRole("button", { name: "Preview minimum disclosure" })
    .click();
  await expect(page.locator("[data-disclosure-preview]")).toContainText(
    "Fields to disclose: name",
  );
  const results = await new AxeBuilder({ page: page as never }).analyze();
  expect(
    results.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
