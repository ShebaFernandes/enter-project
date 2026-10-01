import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const tenantId = "11111111-1111-4111-8111-111111111111";
const reviewId = "22222222-2222-4222-8222-222222222222";
const reviewItemId = "33333333-3333-4333-8333-333333333333";
const etag = '"synthetic-review-etag"';

const html = (body: string) =>
  `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Governance</title><link rel="stylesheet" href="/app/static/dist/assets/app.css"></head><body><main>${body}</main><script type="module" src="/app/static/dist/assets/app.js"></script></body></html>`;

const governanceShell = html(`
<div class="governance-shell" data-governance data-organization data-tenant-id="${tenantId}">
  <header><h1>Tenant governance</h1><p>Administrative metadata only. Candidate content is not available.</p></header>
  <input type="hidden" name="csrfmiddlewaretoken" value="synthetic"><p role="status" data-organization-status></p>
  <div role="tablist" aria-label="Governance sections">
    <button role="tab" aria-selected="true" aria-controls="organization-panel" data-governance-tab="organization">Organization</button>
    <button role="tab" aria-selected="false" aria-controls="audit-panel" data-governance-tab="audit">Audit metadata</button>
    <button role="tab" aria-selected="false" aria-controls="review-panel" data-governance-tab="review">Access reviews</button>
    <button role="tab" aria-selected="false" aria-controls="emergency-panel" data-governance-tab="emergency">Emergency access</button>
  </div>
  <section role="tabpanel" id="organization-panel" data-governance-panel="organization">
    <h2>Business units</h2><form data-business-unit-form><label>Business unit name <input name="name" required></label><label>Description <textarea name="description"></textarea></label><button>Create business unit</button></form><ul data-business-unit-list></ul>
    <h2>Openings</h2><form data-opening-form><label>Business unit ID <input name="business_unit_id"></label><label>Opening title <input name="title"></label><label>Location <input name="location"></label><label>Work mode<select name="work_mode"><option>REMOTE</option></select></label><label>Employment type<input name="employment_type"></label><button>Create opening</button></form><ul data-opening-list></ul>
  </section>
  <section role="tabpanel" id="audit-panel" data-governance-panel="audit" hidden><h2>Redacted audit metadata</h2><ul data-audit-list></ul></section>
  <section role="tabpanel" id="review-panel" data-governance-panel="review" hidden><h2>Access reviews</h2><form data-access-review-form><label>Review type<select name="review_type"><option>MEMBERSHIP</option></select></label><label>Due date<input name="due_at" type="datetime-local"></label><button>Start access review</button></form><p data-review-empty>No access reviews are due.</p><ul data-review-list></ul></section>
  <section role="tabpanel" id="emergency-panel" data-governance-panel="emergency" hidden><h2>Emergency access</h2><p>Scope and expiry are shown without candidate content.</p><script id="emergency-access-data" type="application/json">[{"id":"44444444-4444-4444-8444-444444444444","reason_code":"INCIDENT_SUPPORT","field_scope":["profile_state"],"operation_scope":["READ"],"object_count":1,"status":"ACTIVE","expires_at":"2026-10-01T11:00:00Z"}]</script><ul data-emergency-list></ul></section>
</div>`);

const recruiterShell = html(`
<div class="governance-shell" data-organization data-tenant-id="${tenantId}">
  <h1>Hiring organization</h1><input type="hidden" name="csrfmiddlewaretoken" value="synthetic"><p role="status" data-organization-status></p>
  <ul data-business-unit-list></ul><ul data-opening-list></ul><ul data-synthetic-list></ul>
  <section><h2>Saved searches</h2><p>Opening context comes only from the search criteria context.</p><form data-saved-search-form><label>Saved-search name<input name="name" required></label><label>Search ID<input name="search_id" required></label><button>Save search</button></form><ul data-saved-search-list></ul></section>
</div>`);

async function routeAdminPage(page: import("@playwright/test").Page) {
  await page.route(`**/tenants/${tenantId}/admin/governance/`, (route) =>
    route.fulfill({ body: governanceShell, contentType: "text/html" }),
  );
  await page.route(`**/api/v1/tenants/${tenantId}/business-units`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(`**/api/v1/tenants/${tenantId}/openings`, (route) =>
    route.fulfill({ json: [] }),
  );
}

test("Tenant Admin manages organization and redacted audit metadata without candidate controls", async ({
  page,
}) => {
  await routeAdminPage(page);
  await page.route(`**/api/v1/tenants/${tenantId}/audit-events`, (route) =>
    route.fulfill({
      json: [
        {
          action: "BUSINESS_UNIT_CREATE",
          outcome: "ALLOWED",
          occurred_at: "2026-10-01T10:00:00Z",
        },
      ],
    }),
  );
  await page.route(`**/api/v1/tenants/${tenantId}/access-reviews`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.goto(`/tenants/${tenantId}/admin/governance/`);

  await expect(
    page.getByRole("heading", { name: "Tenant governance" }),
  ).toBeVisible();
  await expect(
    page.getByText("Candidate content is not available"),
  ).toBeVisible();
  await expect(page.getByText("Synthetic candidates")).toHaveCount(0);
  await expect(page.getByText("Saved searches")).toHaveCount(0);
  await page.getByRole("tab", { name: "Audit metadata" }).click();
  await expect(page.getByText("BUSINESS_UNIT_CREATE")).toBeVisible();

  await page.setViewportSize({ width: 320, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const accessibility = await new AxeBuilder({ page: page as never }).analyze();
  expect(
    accessibility.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
});

test("recruiter saved search submits no independent opening and restores authoritative context", async ({
  page,
}) => {
  await page.route(`**/tenants/${tenantId}/recruiter/organization/`, (route) =>
    route.fulfill({ body: recruiterShell, contentType: "text/html" }),
  );
  await page.route(`**/api/v1/tenants/${tenantId}/business-units`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(`**/api/v1/tenants/${tenantId}/openings`, (route) =>
    route.fulfill({ json: [] }),
  );
  await page.route(
    `**/api/v1/tenants/${tenantId}/recruiter-entered-candidates`,
    (route) => route.fulfill({ json: [] }),
  );
  let submitted: Record<string, unknown> = {};
  await page.route(
    `**/api/v1/tenants/${tenantId}/saved-searches`,
    async (route) => {
      if (route.request().method() === "POST")
        submitted = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        json: [
          {
            name: "Opening search",
            criteria: { context: { type: "OPENING", opening_id: "opening-1" } },
            changed_since_save: ["OPENING_STATE"],
          },
        ],
      });
    },
  );
  await page.goto(`/tenants/${tenantId}/recruiter/organization/`);
  await page.getByLabel("Saved-search name").fill("Opening search");
  await page
    .getByLabel("Search ID")
    .fill("55555555-5555-4555-8555-555555555555");
  await page.getByRole("button", { name: "Save search" }).click();
  expect(submitted).toEqual({
    name: "Opening search",
    search_id: "55555555-5555-4555-8555-555555555555",
  });
  await expect(
    page.getByText(/OPENING opening-1 — changed: OPENING_STATE/),
  ).toBeVisible();
});

test("access-review revocation submits the current ETag and records feedback", async ({
  page,
}) => {
  await routeAdminPage(page);
  await page.route(`**/api/v1/tenants/${tenantId}/access-reviews`, (route) =>
    route.fulfill({
      json: [
        {
          id: reviewId,
          review_type: "MEMBERSHIP",
          state: "IN_PROGRESS",
          due_at: "2026-10-08T10:00:00Z",
          remediation_state: "NOT_REQUIRED",
          etag,
          items: [
            {
              id: reviewItemId,
              assignment_type: "MEMBERSHIP",
              evidence: { role: "RECRUITER", status: "ACTIVE" },
              decision: "PENDING",
            },
          ],
        },
      ],
    }),
  );
  let ifMatch = "";
  await page.route(
    `**/api/v1/tenants/${tenantId}/access-reviews/${reviewId}/complete`,
    async (route) => {
      ifMatch = (await route.request().allHeaders())["if-match"] ?? "";
      await route.fulfill({ json: {}, status: 200 });
    },
  );
  await page.goto(`/tenants/${tenantId}/admin/governance/`);
  await page.getByRole("tab", { name: "Access reviews" }).click();
  await page.getByRole("button", { name: "Revoke membership access" }).click();
  await expect(page.getByRole("status")).toContainText("Access revoked");
  expect(ifMatch).toBe(etag);
});

test("emergency metadata exposes minimum scope and supports revocation", async ({
  page,
}) => {
  await routeAdminPage(page);
  let revoked = false;
  await page.route(
    `**/api/v1/tenants/${tenantId}/emergency-access-grants/*/revoke`,
    (route) => {
      revoked = true;
      return route.fulfill({ status: 204 });
    },
  );
  await page.goto(`/tenants/${tenantId}/admin/governance/`);
  await page.getByRole("tab", { name: "Emergency access" }).click();
  await expect(
    page.getByText(/INCIDENT_SUPPORT.*profile_state.*1 scoped object/),
  ).toBeVisible();
  await expect(page.getByText(/resume|email|phone/i)).toHaveCount(0);
  await page.getByRole("button", { name: "Revoke emergency access" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Emergency access revoked",
  );
  expect(revoked).toBe(true);
});
