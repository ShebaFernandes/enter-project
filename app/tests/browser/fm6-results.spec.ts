import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const token = "a".repeat(43);
const fixture = `/app/tests/browser/fixtures/fm6.html#handoff=${token}`;
const search = "00000000-0000-4000-8000-000000000002";
const candidate = "00000000-0000-4000-8000-000000000003";
const criteria = {
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
};
const finding = {
  code: "SHORT_TENURE",
  informational_only: true,
  message: "One confirmed employment period was shorter than six months.",
  evidence: {
    employment_record_id: "synthetic",
    company: "Synthetic Company",
    confirmed_start_date: "2024-01-01",
    confirmed_end_date: "2024-04-01",
    calculated_duration: { calendar_months: 3, remaining_days: 0 },
    calculation_version: "v1",
    evaluated_at: "2026-10-01",
  },
};
const item = {
  candidate_id: candidate,
  summary: {
    name: "Synthetic Candidate",
    current_role: "Software engineer",
    location: { display: "Bengaluru" },
    skills: ["Python"],
    experience_years: null,
  },
  evidence: [{ label: "skill", provenance: "CANDIDATE_REPORTED" }],
  findings: [finding],
  unknowns: ["experience_years"],
};
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/search-handoffs/search-results", (route) =>
    route.fulfill({ json: { search_id: search, criteria } }),
  );
  await page.route("**/search-handoffs/search-results/display", (route) =>
    route.fulfill({
      json: { search_id: search, items: [item], next_cursor: null },
    }),
  );
  await page.route("**/candidates/*?search_id=*", (route) =>
    route.fulfill({
      json: {
        ...item,
        permitted_fields: item.summary,
        candidate_work: { id: "synthetic" },
      },
    }),
  );
});
test("FM6 applied criteria edit stays inside results and never executes merely by opening", async ({
  page,
}) => {
  let executions = 0;
  await page.route("**/searches", (route) => {
    executions++;
    return route.fulfill({ status: 500 });
  });
  await page.route("**/search-handoffs/criteria-review", (route) =>
    route.fulfill({
      json:
        route.request().method() === "POST"
          ? { token: "b".repeat(43) }
          : { criteria, etag: '"review-1"', estimated_count: 1 },
    }),
  );
  await page.goto(fixture);
  await expect(
    page.getByRole("region", { name: "Applied deterministic criteria" }),
  ).toContainText("Python");
  await page
    .getByRole("button", { name: "Adjust criteria", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Criteria restored");
  await expect(page.getByRole("main")).toHaveCount(1);
  await expect(page).toHaveURL(fixture);
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Adjust criteria", exact: true }),
  ).toBeFocused();
  expect(executions).toBe(0);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
test("FM6 results and authorized detail are accessible and responsive", async ({
  page,
}) => {
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.goto("about:blank");
    await page.setViewportSize({ width, height });
    await page.goto(fixture);
    await expect(
      page.getByRole("heading", { name: "Synthetic Candidate" }),
    ).toBeVisible();
    await page.evaluate((value) => {
      document.documentElement.style.zoom = String(value);
    }, zoom);
    await expect(page).toHaveScreenshot(`results-${width}-${zoom}.png`, {
      fullPage: true,
    });
    expect(
      (
        await new AxeBuilder({ page: page as never }).analyze()
      ).violations.filter((v) =>
        ["serious", "critical"].includes(v.impact ?? ""),
      ),
    ).toEqual([]);
    await page.getByRole("button", { name: "View authorized details" }).click();
    await expect(page.getByRole("dialog")).toContainText("Unknown");
    await expect(page.getByRole("dialog")).toContainText("Unavailable");
    await expect(page).toHaveScreenshot(`detail-${width}-${zoom}.png`, {
      fullPage: true,
    });
    expect(
      (
        await new AxeBuilder({ page: page as never }).analyze()
      ).violations.filter((v) =>
        ["serious", "critical"].includes(v.impact ?? ""),
      ),
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "View authorized details" }),
    ).toBeFocused();
  }
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
test("FM6 expired results and revoked candidate reads fail closed", async ({
  page,
}) => {
  await page.goto(fixture);
  await page.route("**/candidates/*?search_id=*", (route) =>
    route.fulfill({ status: 403, json: {} }),
  );
  await page.getByRole("button", { name: "View authorized details" }).click();
  await expect(page.getByRole("dialog")).toContainText("unavailable");
  await expect(
    page.getByRole("dialog").getByText("Software engineer"),
  ).toHaveCount(0);
  await expect(page.getByRole("article")).toHaveCount(0);
  await page.route("**/search-handoffs/search-results", (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("expired");
  await expect(page.getByRole("article")).toHaveCount(0);
});

test("FM6 selection preserves order, uses CSRF and rejects stale overwrite", async ({
  page,
}) => {
  const second = {
    ...item,
    candidate_id: "00000000-0000-4000-8000-000000000004",
    summary: { ...item.summary, name: "Second Candidate" },
    findings: [],
  };
  await page.route("**/search-handoffs/search-results/display", (route) =>
    route.fulfill({
      json: { search_id: search, items: [second, item], next_cursor: null },
    }),
  );
  let selected: string[] = [];
  let stale = false;
  await page.route("**/search-handoffs/comparison-selection", async (route) => {
    const method = route.request().method();
    if (method !== "GET")
      expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    if (method === "POST") {
      selected = route.request().postDataJSON().candidate_ids;
      await route.fulfill({ json: { token: "b".repeat(43) } });
      return;
    }
    if (method === "PATCH") {
      expect(route.request().headers()["if-match"]).toBe('"one"');
      if (stale) {
        await route.fulfill({ status: 409, json: {} });
        return;
      }
      selected = route.request().postDataJSON().candidate_ids;
    }
    await route.fulfill({
      json: { search_id: search, candidate_ids: selected, etag: '"one"' },
    });
  });
  await page.goto(fixture);
  await expect(
    page
      .getByRole("article")
      .getByRole("heading", { level: 3 })
      .filter({ hasText: /Candidate$/ }),
  ).toHaveText(["Second Candidate", "Synthetic Candidate"]);
  await page.getByLabel("Compare Synthetic Candidate").check();
  await page.getByLabel("Compare Second Candidate").check();
  await expect(page.getByRole("status")).toContainText("2 candidates selected");
  expect(selected).toEqual([candidate, second.candidate_id]);
  await page.reload();
  await expect(page.getByLabel("Compare Synthetic Candidate")).toBeChecked();
  stale = true;
  await page.getByLabel("Compare Second Candidate").uncheck();
  await expect(page.getByRole("alert")).toContainText(
    "nothing was silently overwritten",
  );
  await page
    .getByRole("button", { name: "Refresh authorized results" })
    .click();
  await expect(page.getByLabel("Compare Second Candidate")).toBeChecked();
  await page
    .getByRole("button", { name: "With employment information" })
    .click();
  await expect(page.getByRole("article")).toHaveCount(1);
  await page
    .getByRole("button", { name: "All candidates", exact: true })
    .click();
  await expect(page.getByRole("article")).toHaveCount(2);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM6 empty throttled and degraded states do not retain candidate cards", async ({
  page,
}) => {
  await page.route("**/search-handoffs/search-results/display", (route) =>
    route.fulfill({
      json: { search_id: search, items: [], next_cursor: null },
    }),
  );
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "No authorized candidates matched" }),
  ).toBeVisible();
  for (const status of [429, 503]) {
    await page.route("**/search-handoffs/search-results/display", (route) =>
      route.fulfill({ status, json: {} }),
    );
    await page.reload();
    await expect(page.getByRole("alert")).toContainText(
      status === 429 ? "Too many requests" : "unavailable",
    );
    await expect(page.getByRole("article")).toHaveCount(0);
  }
});
