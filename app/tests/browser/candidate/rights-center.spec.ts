import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

async function loadTemplate(page: Page, path: string) {
  const html = await readFile(path, "utf8");
  await page.goto("http://127.0.0.1:4173");
  await page.setContent(`<base href="http://127.0.0.1:4173">${html}`);
  await page.addStyleTag({ path: "static/dist/assets/app.css" });
}

test("candidate profile has accessible employment, consent, resume, and save controls", async ({
  page,
}) => {
  await page.route(/\/api\/v1\/candidate\/profile$/, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        json: {
          full_name: "Synthetic Candidate",
          location: { display: "Pune" },
          experience_years: "2.5",
          skills: ["Python"],
          meaningful_work: "",
          employment_history: [],
        },
        headers: { ETag: '"profile-v1"' },
      });
      return;
    }
    await route.fulfill({
      status: 409,
      json: {
        title: "Stale write",
        current: { full_name: "Latest Stored Name" },
        attempted: { full_name: "Attempted Name" },
        changed_fields: ["full_name"],
        current_etag: '"profile-v2"',
      },
    });
  });
  await loadTemplate(page, "frontend/templates/candidate/profile.html");
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  await expect(
    page.getByRole("heading", { name: "Control your profile" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Employment history" }),
  ).toBeVisible();
  await expect(
    page.getByRole("group", { name: "Who may discover this profile?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save profile" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add employment record" }).click();
  await expect(
    page.getByRole("group", { name: "Employment record" }),
  ).toBeVisible();
  await page.getByLabel("Full name").fill("Attempted Name");
  await page.getByRole("button", { name: "Save profile" }).click();
  await page
    .getByText("Review the latest saved values and your attempted changes")
    .click();
  await expect(page.getByText("Latest Stored Name")).toBeVisible();
  await expect(page.getByText("Attempted Name")).toBeVisible();
  await page.setViewportSize({ width: 320, height: 800 });
  await expect(page.locator("[data-candidate-profile]")).toHaveCSS(
    "display",
    "block",
  );
});

test("rights centre exposes status, history, and explicit deletion confirmation", async ({
  page,
}) => {
  const requestId = "00000000-0000-4000-8000-000000000001";
  await page.route(/\/api\/v1\/candidate\/rights-requests$/, (route) =>
    route.fulfill({
      json: [
        {
          id: requestId,
          request_type: "EXPORT",
          state: "COMPLETED",
          submitted_at: "2026-09-29T10:00:00Z",
          expected_completion_at: "2026-09-30T10:00:00Z",
          completed_at: "2026-09-29T10:05:00Z",
          safe_detail: "Export ready for authenticated download",
          exception_scope: null,
          active_process_exceptions: [],
          support_escalation_available: true,
        },
      ],
    }),
  );
  await page.route(/\/download$/, (route) =>
    route.fulfill({ json: { profile: { full_name: "Synthetic Candidate" } } }),
  );
  await page.route(/\/escalations$/, (route) =>
    route.fulfill({ status: 202, body: "" }),
  );
  await loadTemplate(page, "frontend/templates/candidate/rights-center.html");
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  await expect(
    page.getByRole("heading", { name: "Your data rights" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Request an export" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Request deletion" }),
  ).toBeVisible();
  await expect(page.locator("[data-deletion-dialog]")).toHaveAttribute(
    "aria-labelledby",
    "delete-title",
  );
  await page.getByRole("button", { name: "Request deletion" }).click();
  await expect(
    page.getByRole("dialog", { name: "Confirm profile deletion" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(
    page.getByRole("button", { name: "Download export" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Download export" }).click();
  await expect(page.getByText("Export download prepared.")).toBeVisible();
  await page
    .getByRole("button", { name: "Ask privacy support for help" })
    .click();
  await page
    .getByLabel("Reason for escalation")
    .fill("Synthetic support request");
  await page.getByRole("button", { name: "Send to support" }).click();
  await expect(
    page.getByText("Privacy support escalation recorded."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Request an export" }).focus();
  await expect(
    page.getByRole("button", { name: "Request an export" }),
  ).toBeFocused();
});

const resumeScenarios = [
  {
    name: "success",
    state: { scan_status: "CLEAN", parse_status: "READY", suggestions: [] },
    expected: "Resume processing complete.",
  },
  {
    name: "partial evidence review",
    state: {
      scan_status: "CLEAN",
      parse_status: "REVIEW_REQUIRED",
      suggestions: [
        {
          fact_type: "employment_type",
          value: "PERMANENT",
          confidence: 0.9,
          source_spans: [{ start_offset: 1, end_offset: 10 }],
        },
      ],
    },
    expected: "Review each suggested fact before using it.",
  },
  {
    name: "parse failure",
    state: {
      scan_status: "CLEAN",
      parse_status: "PARSE_FAILED",
      suggestions: [],
    },
    expected: "Resume parsing failed.",
  },
  {
    name: "scan failure",
    state: {
      scan_status: "REJECTED",
      parse_status: "NOT_STARTED",
      suggestions: [],
    },
    expected: "Security scanning did not succeed.",
  },
] as const;

for (const scenario of resumeScenarios) {
  test(`resume ${scenario.name} state preserves manual recovery`, async ({
    page,
  }) => {
    const { state, expected } = scenario;
    const resumeId = "00000000-0000-4000-8000-000000000002";
    await page.route(/\/api\/v1\/candidate\/profile$/, (route) =>
      route.fulfill({
        json: {
          full_name: "Synthetic Candidate",
          location: { display: "Pune" },
          experience_years: "2.5",
          skills: ["Python"],
          meaningful_work: "",
          employment_history: [],
        },
        headers: { ETag: '"profile-v1"' },
      }),
    );
    await page.route(/\/candidate\/resumes\/uploads$/, (route) =>
      route.fulfill({
        status: 201,
        json: {
          resume_id: resumeId,
          upload_url: "http://127.0.0.1:4173/quarantine-upload",
          required_headers: {
            "Content-Type": "application/pdf",
            "x-amz-meta-sha256": "synthetic",
          },
          expires_at: "2026-09-29T10:10:00Z",
        },
      }),
    );
    await page.route(/\/quarantine-upload$/, (route) =>
      route.fulfill({ status: 200 }),
    );
    await page.route(new RegExp(`/candidate/resumes/${resumeId}$`), (route) =>
      route.fulfill({
        json: { id: resumeId, ...state, manual_entry_available: true },
      }),
    );
    await loadTemplate(page, "frontend/templates/candidate/profile.html");
    await page.addScriptTag({
      path: "static/dist/assets/app.js",
      type: "module",
    });
    await page
      .getByLabel("Choose PDF, DOC, or DOCX, up to 10 MB")
      .setInputFiles({
        name: "synthetic-resume.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.7 synthetic"),
      });
    await expect(page.getByText(expected, { exact: false })).toBeVisible();
    if (state.parse_status === "REVIEW_REQUIRED") {
      await expect(
        page.getByText('Suggested value: "PERMANENT"'),
      ).toBeVisible();
      await expect(
        page.getByText("source spans: 1", { exact: false }),
      ).toBeVisible();
    }
  });
}
