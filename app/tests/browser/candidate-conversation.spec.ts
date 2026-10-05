import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const fixture = "/app/tests/browser/fixtures/fm9.html";
const profile = {
  id: "00000000-0000-4000-8000-000000000090",
  full_name: "",
  location: {},
  headline: null,
  current_role: null,
  current_company: null,
  experience_years: "",
  skills: [],
  employment_history: [],
  role_categories: [],
  preferred_locations: [],
  work_arrangements: [],
  meaningful_work: null,
  notice_period: null,
  availability_date: null,
  compensation: null,
  professional_links: [],
  contact_preferences: {},
  profile_state: "DRAFT",
  visibility: { mode: "NOT_LOOKING", version: 1 },
  version: 1,
};

test("resume-first conversation previews parsed facts and preserves edits without saving", async ({
  page,
}) => {
  const writes: string[] = [];
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/api/v1/candidate/profile", (route) => {
    if (route.request().method() !== "GET")
      writes.push(route.request().method());
    return route.fulfill({ json: profile, headers: { ETag: '"v1"' } });
  });
  await page.route("**/api/v1/candidate/resumes/uploads", (route) =>
    route.fulfill({
      json: {
        resume_id: "resume-1",
        upload_url: "http://127.0.0.1:4173/test-upload",
        content_url: "/api/v1/candidate/resumes/resume-1/content",
      },
    }),
  );
  await page.route("**/api/v1/candidate/resumes/resume-1/content", (route) =>
    route.fulfill({ status: 200 }),
  );
  await page.route("**/api/v1/candidate/resumes/resume-1", (route) =>
    route.fulfill({
      json: {
        id: "resume-1",
        scan_status: "CLEAN",
        parse_status: "REVIEW_REQUIRED",
        suggestions: [
          { fact_type: "full_name", value: "Resume Candidate" },
          { fact_type: "skills", value: ["Python", "Django"] },
          { fact_type: "location", value: "Bengaluru" },
        ],
      },
    }),
  );
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Right person. Right problem." }),
  ).toBeVisible();
  await expect(page.getByLabel("Full name", { exact: true })).toHaveCount(0);
  await page.screenshot({
    path: "test-results/candidate-upload-desktop.png",
    fullPage: true,
  });
  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Choose your resume" }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({
    name: "resume.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7 test"),
  });
  await expect(page.locator(".candidate-preview")).toHaveCount(0);
  await expect(page.getByLabel("Full name", { exact: true })).toHaveValue(
    "Resume Candidate",
  );
  await page.getByLabel("Full name", { exact: true }).fill("My chosen name");
  await page.locator("input[type=file]").setInputFiles({
    name: "second.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7 second"),
  });
  await expect(page.getByText("second.pdf", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Full name", { exact: true })).toHaveValue(
    "My chosen name",
  );
  await page.getByRole("button", { name: "30 days", exact: true }).click();
  await expect(page.getByLabel("Notice period", { exact: true })).toHaveValue(
    "30 days",
  );
  await page.getByRole("checkbox", { name: "remote", exact: true }).check();
  await expect(
    page.getByRole("checkbox", { name: "remote", exact: true }),
  ).toBeChecked();
  expect(writes).toEqual([]);
  const accessibility = await new AxeBuilder({ page: page as never })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({
    path: "test-results/candidate-preview-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/candidate-preview-mobile.png",
    fullPage: true,
  });
});

test("missing details link to editable fields and include required opportunity information", async ({
  page,
}) => {
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/api/v1/candidate/profile", (route) =>
    route.fulfill({ json: profile, headers: { ETag: '"v1"' } }),
  );
  await page.goto(fixture);
  await page
    .getByRole("button", { name: "I'll add my details myself" })
    .click();
  await page.getByRole("button", { name: "Add full name" }).click();
  await expect(page.getByLabel("Full name", { exact: true })).toBeFocused();
  await page.getByLabel("Full name", { exact: true }).fill("Test Candidate");
  await expect(page.getByRole("button", { name: "Add full name" })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("progressbar", { name: "Core profile completeness" }),
  ).toHaveAttribute("value", "1");
  await page.getByRole("button", { name: "Add Notice period" }).click();
  await expect(page.getByLabel("Notice period", { exact: true })).toBeFocused();
  await expect(
    page.getByText("Uploading a resume does not make your profile public.", {
      exact: false,
    }),
  ).toBeVisible();
});

test("audience validation prevents partial writes and audience failures can be retried", async ({
  page,
}) => {
  let writes = 0;
  let audienceWrites = 0;
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/api/v1/candidate/profile", (route) => {
    if (route.request().method() === "PATCH") {
      writes++;
      expect(route.request().headers()["if-match"]).toBe(
        writes === 1 ? '"v1"' : '"v2"',
      );
    }
    return route.fulfill({
      json: profile,
      headers: { ETag: writes ? '"v2"' : '"v1"' },
    });
  });
  await page.route("**/api/v1/candidate/visibility", (route) => {
    audienceWrites++;
    return route.fulfill(
      audienceWrites === 1
        ? { status: 503, json: {} }
        : {
            json: { mode: "NOT_LOOKING", version: 2 },
            headers: { ETag: '"v3"' },
          },
    );
  });
  await page.goto(fixture);
  await page
    .getByRole("button", { name: "I'll add my details myself" })
    .click();
  await page
    .getByRole("radio", { name: "Approved recruiters", exact: true })
    .check();
  await page
    .getByRole("button", { name: "Save profile and visibility" })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "no valid company approvals" }),
  ).toBeVisible();
  expect(writes).toBe(0);
  await page.getByRole("radio", { name: "Not looking", exact: true }).check();
  await page
    .getByRole("button", { name: "Save profile and visibility" })
    .click();
  await expect(
    page
      .getByRole("alert")
      .filter({ hasText: "visibility could not be updated" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Save profile and visibility" })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Profile and visibility saved" }),
  ).toBeVisible();
  expect(writes).toBe(2);
});

test("Publish explains missing fields next to the button without submitting", async ({
  page,
}) => {
  let publications = 0;
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/api/v1/candidate/profile", (route) =>
    route.fulfill({ json: profile, headers: { ETag: '"v1"' } }),
  );
  await page.route("**/api/v1/candidate/profile/publish", (route) => {
    publications++;
    return route.fulfill({ json: profile });
  });
  await page.goto(fixture);
  await page
    .getByRole("button", { name: "I'll add my details myself" })
    .click();
  await page
    .getByRole("button", { name: "Publish profile", exact: true })
    .click();
  await expect(page.locator("#profile-action-feedback")).toContainText(
    "Before publishing, add:",
  );
  await expect(page.locator("#profile-action-feedback")).toBeFocused();
  expect(publications).toBe(0);
});

test("Publish displays the server's specific unmet requirement", async ({
  page,
}) => {
  const complete = {
    ...profile,
    full_name: "Test Candidate",
    location: { display: "Bengaluru" },
    current_role: "Engineer",
    experience_years: "2",
    skills: ["Python"],
    notice_period: "30 days",
    meaningful_work: "Built a useful application",
    role_categories: ["Engineer"],
    preferred_locations: ["Bengaluru"],
    work_arrangements: ["REMOTE"],
  };
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/api/v1/candidate/profile", (route) =>
    route.fulfill({ json: complete, headers: { ETag: '"v1"' } }),
  );
  await page.route("**/api/v1/candidate/profile/publish", (route) =>
    route.fulfill({
      status: 422,
      json: { errors: { resume: ["Required before publication."] } },
    }),
  );
  await page.goto(fixture);
  await page
    .getByRole("button", { name: "Review my existing profile" })
    .click();
  await page
    .getByRole("button", { name: "Publish profile", exact: true })
    .click();
  await expect(page.locator("#profile-action-feedback")).toContainText(
    "Publication blocked: Upload a resume",
  );
  await expect(page.locator("#profile-action-feedback")).not.toContainText(
    "consent",
  );
});
