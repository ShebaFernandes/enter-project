import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const tenantId = "00000000-0000-4000-8000-000000000001";
const searchId = "00000000-0000-4000-8000-000000000002";
const firstId = "00000000-0000-4000-8000-000000000003";
const secondId = "00000000-0000-4000-8000-000000000004";
const token = "c".repeat(43);
const fixture = `/app/tests/browser/fixtures/fm8.html#handoff=${token}`;

const field = (state: "KNOWN" | "UNKNOWN" | "UNAVAILABLE", value: unknown) => ({
  state,
  value,
  provenance: state === "KNOWN" ? ["CANDIDATE_REPORTED"] : [],
});
const fields = [
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
];
const response = {
  fields,
  candidates: [
    {
      candidate_id: firstId,
      permitted_fields: {
        name: field("KNOWN", "Synthetic Candidate One"),
        location: field("KNOWN", "Bengaluru"),
        experience: field("KNOWN", "5.00 years"),
        notice_or_availability: field("KNOWN", "30 days"),
        compensation_availability: field("UNAVAILABLE", null),
        skills: field("KNOWN", ["Python", "Django"]),
        employment: field("KNOWN", [
          {
            role_title: "Engineer",
            company: "Synthetic Employer",
            start_date: "2025-01-01",
            end_date: "2025-09-01",
            is_current: false,
          },
        ]),
        preferences: field("KNOWN", ["Remote"]),
        match_evidence: field("KNOWN", ["Python evidence"]),
        informational_findings: field("KNOWN", ["SHORT_TENURE"]),
      },
      evidence: [],
      findings: [
        {
          code: "SHORT_TENURE",
          informational_only: true,
          message: "A confirmed employment record lasted less than 12 months.",
        },
      ],
      unknowns: [],
    },
    {
      candidate_id: secondId,
      permitted_fields: Object.fromEntries(
        fields.map((name) => [
          name,
          name === "name"
            ? field("KNOWN", "Synthetic Candidate Two")
            : field("UNKNOWN", null),
        ]),
      ),
      evidence: [],
      findings: [],
      unknowns: ["location", "skills"],
    },
  ],
};

test.beforeEach(async ({ page }) => {
  let selected = [firstId, secondId];
  let version = 1;
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/search-handoffs/comparison-selection", async (route) => {
    if (route.request().method() === "PATCH") {
      expect(route.request().headers()["if-match"]).toBe(
        `"selection-${version}"`,
      );
      selected = route.request().postDataJSON().candidate_ids;
      version++;
    }
    await route.fulfill({
      json: {
        search_id: searchId,
        candidate_ids: selected,
        etag: `"selection-${version}"`,
      },
    });
  });
  await page.route("**/search-handoffs/comparison-selection/return", (route) =>
    route.fulfill({
      json: {
        return_path: `/tenants/${tenantId}/recruiter/search/?view=results#handoff=${"r".repeat(43)}`,
      },
    }),
  );
  await page.route("**/comparisons", (route) =>
    route.fulfill({ json: response }),
  );
});

test("FM8 restores, reauthorizes, renders evidence, removes safely and uses no storage", async ({
  page,
}) => {
  let comparisons = 0;
  await page.route("**/comparisons", async (route) => {
    comparisons++;
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-tenant-id"]).toBe(tenantId);
    expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    expect(route.request().postDataJSON()).toEqual({
      candidate_ids: [firstId, secondId],
      context_type: "SEARCH",
      context_id: searchId,
    });
    await route.fulfill({ json: response });
  });
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Compare candidates" }),
  ).toBeVisible();
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Synthetic Candidate One" }),
  ).toBeVisible();
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Unknown", { exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/informational only and does not affect ordering/),
  ).toBeVisible();
  await expect(
    page.getByText(/no recommendation or automated hiring conclusion/i),
  ).toBeVisible();
  expect(comparisons).toBe(1);

  await page
    .getByRole("button", { name: "Remove Synthetic Candidate One" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Synthetic Candidate One" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Remove Synthetic Candidate Two" }),
  ).toBeFocused();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM8 clears protected comparison data when current authorization fails", async ({
  page,
}) => {
  await page.route("**/comparisons", (route) =>
    route.fulfill({ status: 403, json: {} }),
  );
  await page.goto(fixture);
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(
    page.getByText("Synthetic Candidate One", { exact: true }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM8 shows safe empty guidance without a valid handoff", async ({
  page,
}) => {
  await page.goto("/app/tests/browser/fixtures/fm8.html");
  await expect(
    page.getByRole("heading", { name: "No candidates selected" }),
  ).toBeVisible();
  await expect(
    page.getByText(/select between two and ten candidates/i),
  ).toBeVisible();
});

test("FM8 comparison responsive and accessibility baselines", async ({
  page,
}) => {
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(fixture);
    await expect(
      page.getByRole("heading", { name: "Synthetic Candidate One" }),
    ).toBeVisible();
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
    await expect(page).toHaveScreenshot(`comparison-${width}-${zoom}.png`, {
      fullPage: true,
    });
  }
});
