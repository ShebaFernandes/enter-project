import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const progress = "/app/tests/browser/fixtures/fm11-progress.html";
const rights = "/app/tests/browser/fixtures/fm11-rights.html";
const applicationId = "00000000-0000-4000-8000-000000000111";
const rightsId = "00000000-0000-4000-8000-000000000112";
const application = {
  id: applicationId,
  opening_title: "Software Engineer",
  candidate_status: "SHORTLISTED",
  status_updated_at: "2026-10-02T08:00:00Z",
  submitted_at: "2026-10-01T08:00:00Z",
  notification_preferences: { email: true, whatsapp: false },
  notification_states: [{ channel: "EMAIL", state: "SENT" }],
  status_history: [
    { candidate_status: "APPLIED", updated_at: "2026-10-01T08:00:00Z" },
    { candidate_status: "SHORTLISTED", updated_at: "2026-10-02T08:00:00Z" },
  ],
  version: 2,
};
const item = {
  id: rightsId,
  request_type: "EXPORT",
  state: "COMPLETED",
  submitted_at: "2026-10-01T08:00:00Z",
  expected_completion_at: "2026-10-02T08:00:00Z",
  completed_at: "2026-10-01T09:00:00Z",
  safe_detail: "Export ready for authenticated download",
  exception_scope: null,
  support_escalation_available: false,
};

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ json: { authenticated: true } }),
  );
});

test("FM11 updates channels with ETag and explicitly confirms withdrawal", async ({
  page,
}) => {
  await page.route("**/api/v1/candidate/applications", (route) =>
    route.fulfill({ json: [application] }),
  );
  await page.route(
    `**/api/v1/candidate/applications/${applicationId}`,
    (route) =>
      route.fulfill({
        headers: { ETag: '"application-v2"' },
        json: application,
      }),
  );
  let preferences = false;
  let conflict = false;
  let withdrawn = false;
  await page.route(
    `**/api/v1/candidate/applications/${applicationId}/notification-preferences`,
    async (route) => {
      preferences = true;
      expect(route.request().headers()["if-match"]).toBe('"application-v2"');
      expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
      expect(route.request().postDataJSON()).toEqual({
        email: true,
        whatsapp: true,
      });
      if (conflict) {
        await route.fulfill({ status: 409, json: { current: application } });
        return;
      }
      await route.fulfill({ json: application });
    },
  );
  await page.route(
    `**/api/v1/candidate/applications/${applicationId}/withdraw`,
    async (route) => {
      withdrawn = true;
      expect(route.request().postDataJSON()).toEqual({
        candidate_status: "WITHDRAWN",
        confirm: true,
      });
      await route.fulfill({
        json: { ...application, candidate_status: "WITHDRAWN" },
      });
    },
  );
  await page.goto(progress);
  await expect(
    page.getByRole("heading", { name: "Your applications" }),
  ).toBeVisible();
  await expect(page.getByText("Applied", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: "WhatsApp" }).check();
  await page.getByRole("button", { name: "Save channels" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "saved" }),
  ).toBeVisible();
  conflict = true;
  await page.getByRole("button", { name: "Save channels" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Nothing was overwritten" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Withdraw this application" }).click();
  await page.getByRole("button", { name: "Keep application" }).click();
  expect(withdrawn).toBe(false);
  await page.getByRole("button", { name: "Withdraw this application" }).click();
  await page.getByRole("button", { name: "Yes, withdraw application" }).click();
  await expect.poll(() => withdrawn).toBe(true);
  expect(preferences).toBe(true);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM11 rights uses explicit deletion consequences and protected requests", async ({
  page,
}) => {
  const states = [
    "PENDING",
    "IN_PROGRESS",
    "HELD",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
  ].map((state, index) => ({
    ...item,
    id: `00000000-0000-4000-8000-${String(index + 120).padStart(12, "0")}`,
    state,
    request_type: index === 3 ? "EXPORT" : "ACCESS",
    support_escalation_available: state === "HELD" || state === "FAILED",
  }));
  await page.route("**/api/v1/candidate/rights-requests", async (route) => {
    if (route.request().method() === "GET")
      return route.fulfill({ json: states });
    expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    expect(route.request().postDataJSON()).toEqual({
      request_type: "DELETE",
      confirm_consequences: true,
      step_up_proof: rightsId,
    });
    return route.fulfill({
      status: 202,
      json: { ...item, request_type: "DELETE", state: "PENDING" },
    });
  });
  await page.goto(rights);
  await expect(
    page.getByRole("heading", { name: "Your data rights" }),
  ).toBeVisible();
  for (const state of [
    "Pending",
    "In progress",
    "Held",
    "Completed",
    "Failed",
    "Cancelled",
  ]) {
    await expect(page.getByText(state, { exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: "Request deletion" }).click();
  const confirm = page.getByRole("button", {
    name: "Confirm deletion request",
  });
  await expect(confirm).toBeDisabled();
  await page.getByLabel("Recent verification reference").fill(rightsId);
  await page.getByLabel(/I understand these consequences/).check();
  await confirm.click();
  await expect(
    page.getByRole("status").filter({ hasText: "accepted" }),
  ).toBeVisible();
});

test("FM11 pages reflow and have no serious accessibility violations", async ({
  page,
}) => {
  await page.route("**/api/v1/candidate/applications", (route) =>
    route.fulfill({ json: [application] }),
  );
  await page.route("**/api/v1/candidate/rights-requests", (route) =>
    route.fulfill({ json: [item] }),
  );
  for (const [name, url] of [
    ["progress", progress],
    ["rights", rights],
  ])
    for (const [width, height, zoom] of [
      [1440, 1000, 1],
      [1024, 768, 1],
      [390, 844, 1],
      [320, 844, 1],
      [1440, 1000, 2],
    ]) {
      await page.setViewportSize({ width, height });
      await page.goto(url);
      await page.locator("html").evaluate((node, factor) => {
        node.style.zoom = String(factor);
      }, zoom);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect(
        (
          await new AxeBuilder({ page: page as never }).analyze()
        ).violations.filter((v) =>
          ["serious", "critical"].includes(v.impact ?? ""),
        ),
      ).toEqual([]);
      await expect(page).toHaveScreenshot(`${name}-${width}-${zoom}x.png`, {
        fullPage: true,
        animations: "disabled",
      });
    }
});
