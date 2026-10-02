import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const fixture = "/app/tests/browser/fixtures/fm9.html";
const employmentId = "00000000-0000-4000-8000-000000000091";
const tenantId = "00000000-0000-4000-8000-000000000092";
const resumeId = "00000000-0000-4000-8000-000000000093";

const profile = {
  id: "00000000-0000-4000-8000-000000000090",
  full_name: "Synthetic Candidate",
  location: { display: "Pune" },
  headline: "Backend engineer",
  current_role: "Software Engineer",
  current_company: "Synthetic Employer",
  experience_years: "5.00",
  skills: ["Python", "Django"],
  employment_history: [
    {
      id: employmentId,
      company: "Synthetic Employer",
      role_title: "Software Engineer",
      start_date: "2022-01-01",
      end_date: null,
      start_date_state: "CONFIRMED",
      end_date_state: "MISSING",
      is_current: true,
      employment_type: "PERMANENT",
      employment_type_state: "CONFIRMED",
      provenance: "CANDIDATE_REPORTED",
      confidence: null,
      source_spans: [],
      version: 1,
    },
  ],
  role_categories: ["Software engineer"],
  preferred_locations: ["Pune", "Remote"],
  work_arrangements: ["REMOTE", "HYBRID"],
  meaningful_work: "Accessible public-interest software.",
  notice_period: "30 days",
  availability_date: null,
  compensation: null,
  professional_links: [],
  contact_preferences: {},
  profile_state: "DRAFT",
  visibility: {
    mode: "APPROVED_RECRUITERS",
    approved_tenant_ids: [tenantId],
    matching_preferences: {},
    version: 1,
  },
  version: 1,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route(/\/api\/v1\/candidate\/profile$/, async (route) => {
    await route.fulfill({ json: profile, headers: { ETag: '"profile-v1"' } });
  });
  await page.route("**/api/v1/candidate/visibility", (route) =>
    route.fulfill({
      json: { ...profile.visibility, version: 2 },
      headers: { ETag: '"profile-v2"' },
    }),
  );
  await page.route("**/api/v1/candidate/profile/publish", (route) =>
    route.fulfill({
      json: { ...profile, profile_state: "PUBLISHED", version: 3 },
      headers: { ETag: '"profile-v3"' },
    }),
  );
});

test("FM9 loads candidate-owned facts and saves with CSRF, ETag and explicit consent", async ({
  page,
}) => {
  let saved = false;
  let visibilitySaved = false;
  await page.route(/\/api\/v1\/candidate\/profile$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: profile, headers: { ETag: '"profile-v1"' } });
      return;
    }
    saved = true;
    expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    expect(route.request().headers()["if-match"]).toBe('"profile-v1"');
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    const body = route.request().postDataJSON();
    expect(body.full_name).toBe("Synthetic Candidate Updated");
    expect(body.employment_history[0].id).toBe(employmentId);
    await route.fulfill({
      json: { ...profile, ...body, version: 2 },
      headers: { ETag: '"profile-v2"' },
    });
  });
  await page.route("**/api/v1/candidate/visibility", async (route) => {
    visibilitySaved = true;
    expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    expect(route.request().headers()["if-match"]).toBe('"profile-v2"');
    expect(route.request().postDataJSON()).toMatchObject({
      mode: "APPROVED_RECRUITERS",
      approved_tenant_ids: [tenantId],
    });
    await route.fulfill({
      json: { ...profile.visibility, version: 2 },
      headers: { ETag: '"profile-v3"' },
    });
  });

  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Control your profile" }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Full name", exact: true }),
  ).toHaveValue("Synthetic Candidate");
  await expect(
    page.getByRole("group", { name: "Employment record 1" }),
  ).toBeVisible();
  await expect(
    page.getByText("Candidate reported", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Full name").fill("Synthetic Candidate Updated");
  await page
    .getByRole("button", { name: "Save profile and visibility" })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Profile and visibility saved" }),
  ).toBeVisible();
  expect(saved).toBe(true);
  expect(visibilitySaved).toBe(true);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM9 exposes stale-write reconciliation and never overwrites automatically", async ({
  page,
}) => {
  await page.route(/\/api\/v1\/candidate\/profile$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: profile, headers: { ETag: '"profile-v1"' } });
      return;
    }
    await route.fulfill({
      status: 409,
      headers: { ETag: '"profile-v2"' },
      json: {
        title: "Information changed",
        current: { full_name: "Latest Stored Name" },
        attempted: { full_name: "Attempted Name" },
        changed_fields: ["full_name"],
        current_etag: '"profile-v2"',
      },
    });
  });
  await page.goto(fixture);
  await page.getByLabel("Full name").fill("Attempted Name");
  await page
    .getByRole("button", { name: "Save profile and visibility" })
    .click();
  await expect(
    page.getByRole("region", { name: "Resolve changed information" }),
  ).toBeFocused();
  await expect(page.getByText(/Stored: Latest Stored Name/)).toBeVisible();
  await expect(page.getByText(/attempted: Attempted Name/)).toBeVisible();
  await expect(page.getByText("Profile and visibility saved")).toHaveCount(0);
});

test("FM9 resume stays quarantined and parse failure keeps manual entry available", async ({
  page,
}) => {
  await page.route("**/api/v1/candidate/resumes/uploads", async (route) => {
    expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    await route.fulfill({
      status: 201,
      json: {
        resume_id: resumeId,
        upload_url: "http://127.0.0.1:4173/quarantine-upload",
        required_headers: { "Content-Type": "application/pdf" },
        expires_at: "2026-10-02T13:00:00Z",
      },
    });
  });
  await page.route("**/quarantine-upload", (route) =>
    route.fulfill({ status: 200 }),
  );
  await page.route(`**/api/v1/candidate/resumes/${resumeId}`, (route) =>
    route.fulfill({
      json: {
        id: resumeId,
        scan_status: "CLEAN",
        parse_status: "PARSE_FAILED",
        manual_entry_available: true,
        suggestions: [],
      },
    }),
  );
  await page.goto(fixture);
  await page.getByLabel("Choose PDF, DOC, or DOCX, up to 10 MB").setInputFiles({
    name: "synthetic-resume.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7 synthetic"),
  });
  await expect(
    page.getByRole("status").filter({ hasText: "Resume parsing failed" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Continue with manual profile entry" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /download/i })).toHaveCount(0);
});

test("FM9 resume drop fills only candidate-approved profile suggestions", async ({
  page,
}) => {
  await page.route("**/api/v1/candidate/resumes/uploads", (route) =>
    route.fulfill({
      status: 201,
      json: {
        resume_id: resumeId,
        upload_url: "http://127.0.0.1:4173/quarantine-upload",
        required_headers: { "Content-Type": "application/pdf" },
      },
    }),
  );
  await page.route("**/quarantine-upload", (route) =>
    route.fulfill({ status: 200 }),
  );
  await page.route(`**/api/v1/candidate/resumes/${resumeId}`, (route) =>
    route.fulfill({
      json: {
        id: resumeId,
        scan_status: "CLEAN",
        parse_status: "REVIEW_REQUIRED",
        suggestions: [
          {
            id: "suggestion-name",
            fact_type: "full_name",
            value: "Resume Candidate",
            confidence: 0.99,
            source_spans: [{ start_offset: 0, end_offset: 16 }],
          },
          {
            id: "suggestion-location",
            fact_type: "location",
            value: { display: "Bengaluru" },
            confidence: 0.92,
            source_spans: [{ start_offset: 17, end_offset: 26 }],
          },
          {
            id: "suggestion-skills",
            fact_type: "skills",
            value: ["Python", "Django", "PostgreSQL"],
            confidence: 0.9,
            source_spans: [{ start_offset: 27, end_offset: 54 }],
          },
          {
            id: "suggestion-unscoped-employment-type",
            fact_type: "employment_type",
            value: "PERMANENT",
            confidence: 0.88,
            source_spans: [{ start_offset: 55, end_offset: 64 }],
          },
        ],
      },
    }),
  );

  await page.goto(fixture);
  await page.locator("[data-resume-drop-zone]").evaluate((element) => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File(["%PDF-1.7 synthetic"], "synthetic-resume.pdf", {
        type: "application/pdf",
      }),
    );
    element.dispatchEvent(
      new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer,
      }),
    );
  });

  await expect(
    page.getByRole("heading", { name: "Review resume suggestions" }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Full name", exact: true }),
  ).toHaveValue("Synthetic Candidate");
  await expect(page.getByLabel("Use suggested full name")).not.toBeChecked();
  await expect(page.getByText("Manual review required")).toBeVisible();
  await expect(page.getByLabel("Use suggested employment type")).toHaveCount(0);
  await page.getByRole("button", { name: "Select all suggestions" }).click();
  await page
    .getByRole("button", { name: "Apply 3 selected suggestions" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Full name", exact: true }),
  ).toHaveValue("Resume Candidate");
  await expect(
    page.getByRole("textbox", { name: "Location", exact: true }),
  ).toHaveValue("Bengaluru");
  await expect(
    page.getByRole("textbox", { name: "Skills", exact: true }),
  ).toHaveValue("Python, Django, PostgreSQL");
  await expect(
    page.getByRole("status").filter({
      hasText: "3 resume suggestions added to your editable profile",
    }),
  ).toBeVisible();
});

test("FM9 profile responsive and accessibility baselines", async ({ page }) => {
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(fixture);
    await expect(page.getByLabel("Full name")).toHaveValue(
      "Synthetic Candidate",
    );
    await page.evaluate((value) => {
      document.documentElement.style.zoom = String(value);
    }, zoom);
    expect(
      (
        await new AxeBuilder({ page: page as never }).analyze()
      ).violations.filter((item) =>
        ["serious", "critical"].includes(item.impact ?? ""),
      ),
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page).toHaveScreenshot(`profile-${width}-${zoom}.png`, {
      fullPage: true,
    });
  }
});
