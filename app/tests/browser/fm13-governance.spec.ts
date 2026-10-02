import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const fixture = "/app/tests/browser/fixtures/fm13.html";
const tenant = "00000000-0000-4000-8000-000000000001";
const reviewId = "00000000-0000-4000-8000-000000000131";
const ownerId = "00000000-0000-4000-8000-000000000135";
const etag = '"review-v1"';
const base = `/api/v1/tenants/${tenant}`;

const review = {
  id: reviewId,
  review_type: "MEMBERSHIP",
  state: "IN_PROGRESS",
  due_at: "2026-10-09T10:00:00Z",
  completed_at: null,
  remediation_state: "NOT_REQUIRED",
  decision_counts: {},
  etag,
  version: 1,
  items: [
    {
      id: "00000000-0000-4000-8000-000000000132",
      assignment_type: "MEMBERSHIP",
      evidence: { role: "RECRUITER", status: "ACTIVE" },
      decision: "PENDING",
      finding: "",
      remediation_state: "NOT_REQUIRED",
      exception_expires_at: null,
    },
    {
      id: "00000000-0000-4000-8000-000000000133",
      assignment_type: "PURPOSE_GRANT",
      evidence: { purpose: "RECRUITING", status: "ACTIVE" },
      decision: "PENDING",
      finding: "",
      remediation_state: "NOT_REQUIRED",
      exception_expires_at: null,
    },
    {
      id: "00000000-0000-4000-8000-000000000134",
      assignment_type: "AUDIT_ACCESS",
      evidence: { role: "TENANT_ADMIN", status: "ACTIVE" },
      decision: "PENDING",
      finding: "",
      remediation_state: "NOT_REQUIRED",
      exception_expires_at: null,
    },
  ],
};

async function mockBase(page: Page) {
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ json: { authenticated: true } }),
  );
  await page.route(`**${base}/audit-events`, (route) =>
    route.fulfill({
      json: [
        {
          id: "00000000-0000-4000-8000-000000000137",
          occurred_at: "2026-10-02T10:00:00Z",
          actor_id: "00000000-0000-4000-8000-000000000138",
          effective_role: "TENANT_ADMIN",
          action: "ACCESS_REVIEW_CREATE",
          target_type: "access_review",
          outcome: "ALLOWED",
          reason_code: null,
          correlation_id: "synthetic-correlation",
        },
      ],
    }),
  );
  await page.route(`**${base}/access-reviews`, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: [review] })
      : route.fallback(),
  );
}

test("FM13 loads redacted audited governance without candidate content or browser storage", async ({
  page,
}) => {
  await mockBase(page);
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Tenant governance" }),
  ).toBeVisible();
  await expect(
    page.getByText(/does not grant access to candidate content/i),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Audit metadata" }).click();
  await expect(page.getByText("ACCESS_REVIEW_CREATE")).toBeVisible();
  await expect(page.getByText(/ALLOWED/)).toBeVisible();
  await expect(page.getByText(/resume|email|phone/i)).toHaveCount(0);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM13 creates a tenant access review with protected request headers", async ({
  page,
}) => {
  await mockBase(page);
  let submitted: Record<string, unknown> = {};
  await page.route(`**${base}/access-reviews`, async (route) => {
    if (route.request().method() === "GET") return route.fallback();
    expect(route.request().headers()["x-tenant-id"]).toBe(tenant);
    expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    submitted = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: review });
  });
  await page.goto(fixture);
  await page.getByRole("tab", { name: "Access reviews" }).click();
  await page.getByLabel("Review type").selectOption("AUDIT_ACCESS");
  await page.getByLabel("Due date").fill("2026-10-10T12:00");
  await page.getByRole("button", { name: "Start access review" }).click();
  await expect(page.getByText("Access review started.")).toBeVisible();
  expect(submitted).toEqual({
    review_type: "AUDIT_ACCESS",
    due_at: "2026-10-10T12:00",
  });
});

test("FM13 confirms retain, revoke and bounded exception decisions with the current ETag", async ({
  page,
}) => {
  await mockBase(page);
  let body: Record<string, unknown> = {};
  let calls = 0;
  await page.route(
    `**${base}/access-reviews/${reviewId}/complete`,
    async (route) => {
      calls += 1;
      expect(route.request().headers()["if-match"]).toBe(etag);
      body = route.request().postDataJSON();
      await route.fulfill({
        status: calls === 1 ? 409 : 200,
        json:
          calls === 1
            ? { current: review }
            : { ...review, state: "COMPLETED", version: 2, items: [] },
      });
    },
  );
  await page.goto(fixture);
  await page.getByRole("tab", { name: "Access reviews" }).click();
  await page.getByLabel("Decision for item 1").selectOption("RETAIN");
  await page.getByLabel("Decision for item 2").selectOption("REVOKE");
  await page.getByLabel("Finding for item 2").fill("Access no longer required");
  await page.getByLabel("Decision for item 3").selectOption("EXCEPTION");
  await page.getByLabel("Exception owner ID for item 3").fill(ownerId);
  await page.getByLabel("Exception expiry for item 3").fill("2026-10-12T12:00");
  await page.getByLabel("Finding for item 3").fill("Temporary audit coverage");
  await page.getByRole("button", { name: "Complete review" }).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  expect(calls).toBe(0);
  await page.getByRole("button", { name: "Complete review" }).click();
  await page.getByRole("button", { name: "Confirm decisions" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Review changed; no decisions were applied",
  );
  await page.getByRole("button", { name: "Complete review" }).click();
  await page.getByRole("button", { name: "Confirm decisions" }).click();
  await expect(page.getByRole("status")).toContainText("Review completed");
  expect(body).toMatchObject({
    decisions: [
      { decision: "RETAIN" },
      { decision: "REVOKE", finding: "Access no longer required" },
      {
        decision: "EXCEPTION",
        finding: "Temporary audit coverage",
        exception_owner_id: ownerId,
      },
    ],
  });
});

test("FM13 emergency access cancellation is safe and confirmed revocation is protected", async ({
  page,
}) => {
  await mockBase(page);
  let calls = 0;
  await page.route(
    `**${base}/emergency-access-grants/*/revoke`,
    async (route) => {
      calls += 1;
      expect(route.request().headers()["x-tenant-id"]).toBe(tenant);
      expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      await route.fulfill({ status: 204 });
    },
  );
  await page.goto(fixture);
  await page.getByRole("tab", { name: "Emergency access" }).click();
  await expect(
    page.getByText(/INCIDENT_SUPPORT.*profile_state.*1 scoped object/i),
  ).toBeVisible();
  await page.getByRole("button", { name: "Revoke emergency access" }).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  expect(calls).toBe(0);
  await page.getByRole("button", { name: "Revoke emergency access" }).click();
  await page.getByRole("button", { name: "Confirm revocation" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Emergency access revoked",
  );
  expect(calls).toBe(1);
});

test("FM13 governance reflows and passes serious accessibility checks", async ({
  page,
}) => {
  await mockBase(page);
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(fixture);
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
      ).violations.filter((item) =>
        ["serious", "critical"].includes(item.impact ?? ""),
      ),
    ).toEqual([]);
    await expect(page).toHaveScreenshot(`governance-${width}-${zoom}x.png`, {
      fullPage: true,
      animations: "disabled",
    });
  }
});
