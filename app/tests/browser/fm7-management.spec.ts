import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
const fixture =
  "/app/tests/browser/fixtures/fm7.html?search_id=00000000-0000-4000-8000-000000000002";
const work = {
  id: "work",
  internal_status: "SOURCED",
  shortlisted: false,
  structured_reasons: [],
  explanatory_note: null,
  version: 1,
};
test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/candidates/*?search_id=*", (route) =>
    route.fulfill({
      json: {
        candidate_work: work,
        permitted_fields: { name: "Synthetic Candidate", skills: ["Python"] },
        evidence: [],
        findings: [],
        unknowns: [],
      },
    }),
  );
  await page.route("**/candidate-work/work", (route) =>
    route.fulfill({ json: work, headers: { ETag: '"work-1"' } }),
  );
  await page.route("**/candidate-work/work/notes", (route) =>
    route.fulfill({ json: [] }),
  );
});
test("FM7 notes use trusted tenant and CSRF; cancellation never mutates", async ({
  page,
}) => {
  let writes = 0;
  await page.route("**/candidate-work/work/notes", async (route) => {
    if (route.request().method() === "POST") {
      writes++;
      expect(route.request().headers()["x-tenant-id"]).toBe(
        "00000000-0000-4000-8000-000000000001",
      );
      expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      expect(route.request().postDataJSON().body).toBe("Synthetic note");
    }
    await route.fulfill({ json: [] });
  });
  await page.goto(fixture);
  await page
    .getByLabel("Recruiter note", { exact: true })
    .fill("Synthetic note");
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Note saved");
  await page
    .getByLabel("Internal status", { exact: true })
    .selectOption("NOT_RELEVANT");
  await page.getByLabel("Wrong location", { exact: true }).check();
  await page.getByRole("button", { name: "Save internal status" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect(writes).toBe(1);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
test("FM7 fresh authorization failure clears protected content before mutation", async ({
  page,
}) => {
  await page.goto(fixture);
  await page
    .getByLabel("Recruiter note", { exact: true })
    .fill("Private draft");
  let writes = 0;
  await page.route("**/candidates/*?search_id=*", (route) =>
    route.fulfill({ status: 403, json: {} }),
  );
  await page.route("**/candidate-work/work/notes", (route) => {
    writes++;
    return route.fulfill({ json: [] });
  });
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(
    page.getByText("Synthetic Candidate", { exact: true }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Recruiter note", { exact: true })).toHaveCount(
    0,
  );
  expect(writes).toBe(0);
});
test("FM7 management responsive and accessibility baselines", async ({
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
      page.getByLabel("Recruiter note", { exact: true }),
    ).toBeVisible();
    await page.evaluate((z) => {
      document.documentElement.style.zoom = String(z);
    }, zoom);
    await expect(page.getByRole("main")).toHaveCount(1);
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
    await expect(page).toHaveScreenshot(`management-${width}-${zoom}.png`, {
      fullPage: true,
    });
  }
});

test("FM7 disclosure requires a destination/field preview and revalidates on confirmation", async ({
  page,
}) => {
  let confirmations = 0;
  await page.route("**/disclosures/preview", (route) =>
    route.fulfill({
      json: {
        preview_id: "preview",
        preview_hash: "a".repeat(64),
        destination: { type: "HIRING_TEAM", label: "Approved team" },
        permitted_fields: ["name"],
        excluded_fields: ["phone"],
        state: "PREVIEWED",
        expires_at: "2026-10-01",
      },
    }),
  );
  await page.route("**/candidates/*/disclosures", (route) => {
    confirmations++;
    return route.fulfill({ status: 403, json: {} });
  });
  await page.goto(fixture);
  await page
    .getByLabel("Destination identifier", { exact: true })
    .fill("authorized-team");
  await page
    .getByLabel("Destination label", { exact: true })
    .fill("Approved team");
  await page.getByLabel("name", { exact: true }).check();
  await page.getByLabel("phone", { exact: true }).check();
  await page.getByRole("button", { name: "Preview disclosure" }).click();
  await expect(page.getByRole("dialog")).toContainText(
    "Permitted fields: name",
  );
  await expect(page.getByRole("dialog")).toContainText(
    "Excluded fields: phone",
  );
  expect(confirmations).toBe(0);
  await page
    .getByRole("button", { name: "Confirm disclosure", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(confirmations).toBe(1);
});

test("FM7 stale status never overwrites without explicit reconciliation", async ({
  page,
}) => {
  let writes = 0;
  await page.route("**/candidate-work/work", (route) => {
    if (route.request().method() === "GET")
      return route.fulfill({ json: work, headers: { ETag: '"work-1"' } });
    writes++;
    expect(route.request().headers()["if-match"]).toBe('"work-1"');
    return route.fulfill({
      status: 409,
      json: {
        current: { ...work, internal_status: "CONTACTED" },
        attempted: { internal_status: "SHORTLISTED" },
        changed_fields: ["internal_status"],
        current_etag: '"work-2"',
      },
    });
  });
  await page.goto(fixture);
  await page
    .getByLabel("Internal status", { exact: true })
    .selectOption("SHORTLISTED");
  await page.getByRole("button", { name: "Save internal status" }).click();
  await expect(
    page.getByRole("region", { name: "Resolve changed information" }),
  ).toBeFocused();
  expect(writes).toBe(1);
  await page.getByRole("button", { name: "Review and merge" }).click();
  await expect(page.getByRole("status")).toContainText("explicitly save");
  expect(writes).toBe(1);
});

test("FM7 application publication needs a separate explicit confirmation", async ({
  page,
}) => {
  await page.route("**/candidates/*?search_id=*", (route) =>
    route.fulfill({
      json: {
        candidate_work: work,
        permitted_fields: { name: "Synthetic Candidate" },
        evidence: [],
        findings: [],
        unknowns: [],
        application_context: {
          id: "application",
          etag: '"application-1"',
          internal_status: "SCREENING",
          candidate_status: "APPLIED",
        },
      },
    }),
  );
  let publishes = 0;
  await page.route("**/applications/application/status-preview", (route) => {
    expect(route.request().headers()["if-match"]).toBe('"application-1"');
    return route.fulfill({
      json: {
        preview_id: "preview",
        suggested_candidate_status: "RECRUITER_INTERESTED",
      },
      headers: { ETag: '"application-2"' },
    });
  });
  await page.route("**/applications/application/status-publish", (route) => {
    publishes++;
    expect(route.request().headers()["if-match"]).toBe('"application-2"');
    expect(route.request().postDataJSON()).toEqual({
      preview_id: "preview",
      candidate_status: "RECRUITER_INTERESTED",
      confirm: true,
      notify_channels: [],
    });
    return route.fulfill({ json: {} });
  });
  await page.goto(fixture);
  await page
    .getByRole("button", { name: "Preview candidate-facing status" })
    .click();
  await expect(
    page.getByLabel("Candidate-facing status", { exact: true }),
  ).toHaveValue("RECRUITER_INTERESTED");
  expect(publishes).toBe(0);
  await page
    .getByRole("button", { name: "Confirm publication", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "published after confirmation",
  );
  expect(publishes).toBe(1);
});

test("FM7 application notes and internal status never update candidate work", async ({
  page,
}) => {
  await page.route("**/candidates/*?search_id=*", (route) =>
    route.fulfill({
      json: {
        candidate_work: work,
        permitted_fields: { name: "Synthetic Candidate" },
        evidence: [],
        findings: [],
        unknowns: [],
        application_context: {
          id: "application",
          etag: '"application-1"',
          internal_status: "SCREENING",
          candidate_status: "APPLIED",
        },
      },
    }),
  );
  let appNotes = 0,
    appStatuses = 0,
    workWrites = 0;
  await page.route("**/applications/application/notes", (route) => {
    if (route.request().method() === "POST") appNotes++;
    return route.fulfill({ json: [] });
  });
  await page.route("**/applications/application/internal-status", (route) => {
    appStatuses++;
    expect(route.request().method()).toBe("PUT");
    expect(route.request().headers()["if-match"]).toBe('"application-1"');
    return route.fulfill({
      json: {
        id: "application",
        internal_status: "INTERVIEWING",
        candidate_status: "APPLIED",
      },
      headers: { ETag: '"application-2"' },
    });
  });
  await page.route("**/candidate-work/work", (route) => {
    if (route.request().method() !== "GET") workWrites++;
    return route.fulfill({ json: work, headers: { ETag: '"work-1"' } });
  });
  await page.goto(fixture);
  await page
    .getByLabel("Management record", { exact: true })
    .selectOption("APPLICATION");
  await expect(page.getByLabel("Internal status", { exact: true })).toHaveValue(
    "SCREENING",
  );
  await page
    .getByLabel("Recruiter note", { exact: true })
    .fill("Application-only note");
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Note saved");
  await page
    .getByLabel("Internal status", { exact: true })
    .selectOption("INTERVIEWING");
  await page.getByRole("button", { name: "Save internal status" }).click();
  await expect(page.getByRole("status")).toContainText("Internal status saved");
  expect([appNotes, appStatuses, workWrites]).toEqual([1, 1, 0]);
  await expect(page.getByLabel("Shortlisted", { exact: true })).toHaveCount(0);
});

test("FM7 pending disclosure is not described as delivered; dialog keyboard cancellation is safe", async ({
  page,
}) => {
  const disclosure = {
    preview_id: "preview",
    preview_hash: "a".repeat(64),
    destination: { type: "HIRING_TEAM", label: "Approved team" },
    permitted_fields: ["name"],
    excluded_fields: [],
    state: "PREVIEWED",
    expires_at: "2026-10-01",
  };
  let sends = 0;
  await page.route("**/disclosures/preview", (route) =>
    route.fulfill({ json: disclosure }),
  );
  await page.route("**/candidates/*/disclosures", (route) => {
    sends++;
    return route.fulfill({
      status: 202,
      json: { ...disclosure, state: "PENDING", result_category: null },
    });
  });
  await page.goto(fixture);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to main content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByLabel("Destination identifier", { exact: true }).fill("team");
  await page
    .getByLabel("Destination label", { exact: true })
    .fill("Approved team");
  await page.getByLabel("name", { exact: true }).check();
  await page.getByRole("button", { name: "Preview disclosure" }).click();
  await expect(
    page.getByRole("button", { name: "Close dialog" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(
    page.getByRole("button", { name: "Cancel disclosure" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  expect(sends).toBe(0);
  await page.getByRole("button", { name: "Preview disclosure" }).click();
  await page
    .getByRole("button", { name: "Confirm disclosure", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Disclosure result: pending",
  );
  expect(sends).toBe(1);
});

test("FM7 loading, rate limited and unavailable states never show a cached profile", async ({
  page,
}) => {
  await page.route("**/candidate-work/work", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.fulfill({ status: 429, json: {} });
  });
  await page.goto(fixture);
  await expect(
    page.getByRole("status").filter({ hasText: "Loading current authorized" }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Too many requests");
  await expect(
    page.getByText("Synthetic Candidate", { exact: true }),
  ).toHaveCount(0);
  await page.route("**/candidate-work/work", (route) =>
    route.fulfill({ status: 503, json: {} }),
  );
  await page
    .getByRole("button", { name: "Reload current information" })
    .click();
  await expect(page.getByRole("alert")).toContainText("Unable to complete");
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
