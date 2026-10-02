import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const jobsFixture = "/app/tests/browser/fixtures/fm10-jobs.html";
const roleFixture = "/app/tests/browser/fixtures/fm10-role.html";
const openingId = "00000000-0000-4000-8000-000000000101";

const opening = {
  id: openingId,
  title: "Software Engineer",
  description:
    "Build reliable, accessible hiring software with a thoughtful product team.",
  location: "Bengaluru",
  work_mode: "REMOTE",
  employment_type: "PERMANENT",
  published_at: "2026-10-02T08:00:00Z",
  closes_at: null,
  application_url: `/roles/${openingId}/`,
};

test("FM10 public jobs lists only API-provided roles and handles an empty directory", async ({
  page,
}) => {
  await page.route("**/api/v1/public/openings?limit=25", (route) =>
    route.fulfill({ json: { items: [opening], next_cursor: null } }),
  );
  await page.route(`**/api/v1/public/openings/${openingId}`, (route) =>
    route.fulfill({ json: opening }),
  );
  await page.goto(jobsFixture);
  await expect(
    page.getByRole("heading", { name: "Find work that matters" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: opening.title }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: `View ${opening.title}` }),
  ).toHaveAttribute("href", opening.application_url);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);

  await page.route("**/api/v1/public/openings?limit=25", (route) =>
    route.fulfill({ json: { items: [], next_cursor: null } }),
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "No open roles right now" }),
  ).toBeVisible();
});

test("FM10 role submits explicit consent and channel preferences with protected headers", async ({
  page,
}) => {
  await page.route(`**/api/v1/public/openings/${openingId}`, (route) =>
    route.fulfill({ json: opening }),
  );
  let submitted = false;
  await page.route("**/api/v1/candidate/applications", async (route) => {
    submitted = true;
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    expect(route.request().postDataJSON()).toMatchObject({
      opening_id: openingId,
      resume_id: "00000000-0000-4000-8000-000000000102",
      consent_record_id: "00000000-0000-4000-8000-000000000103",
      notification_preferences: { email: true, whatsapp: false },
      answers: { motivation: "Accessible systems are meaningful to me." },
    });
    await route.fulfill({
      status: 201,
      headers: { ETag: '"application-v1"' },
      json: { id: "00000000-0000-4000-8000-000000000104" },
    });
  });

  await page.goto(roleFixture);
  await expect(
    page.getByRole("heading", { name: opening.title }),
  ).toBeVisible();
  await page.getByLabel("Full name").fill("Synthetic Candidate");
  await page.getByLabel("Verified email").fill("candidate@example.test");
  await page
    .getByLabel("Why are you interested?")
    .fill("Accessible systems are meaningful to me.");
  await page.getByRole("checkbox", { name: "Email", exact: true }).check();
  await page.getByLabel(/I consent to use of my profile/).check();
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("status")).toContainText("Application submitted");
  expect(submitted).toBe(true);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM10 signed-out role remains readable but cannot submit", async ({
  page,
}) => {
  const html = await (
    await fetch("http://127.0.0.1:4173" + roleFixture)
  ).text();
  await page.route("**/fm10-role.html", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: html
        .replace(/,\s*"resumeId":\s*"00000000-0000-4000-8000-000000000102"/, "")
        .replace(
          /,\s*"consentId":\s*"00000000-0000-4000-8000-000000000103"/,
          "",
        ),
    }),
  );
  await page.route(`**/api/v1/public/openings/${openingId}`, (route) =>
    route.fulfill({ json: opening }),
  );
  await page.goto(roleFixture);
  await expect(page.getByText(opening.description)).toBeVisible();
  await page.getByLabel("Full name").fill("Synthetic Candidate");
  await page.getByLabel("Verified email").fill("candidate@example.test");
  await page.getByLabel(/I consent to use of my profile/).check();
  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Sign in and confirm role-specific consent",
  );
});

test("FM10 pages reflow at required viewports and pass serious accessibility checks", async ({
  page,
}) => {
  await page.route("**/api/v1/public/openings?limit=25", (route) =>
    route.fulfill({ json: { items: [opening], next_cursor: null } }),
  );
  await page.route(`**/api/v1/public/openings/${openingId}`, (route) =>
    route.fulfill({ json: opening }),
  );
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(jobsFixture);
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
    await expect(page).toHaveScreenshot(`jobs-${width}-${zoom}x.png`, {
      fullPage: true,
      animations: "disabled",
    });

    await page.goto(roleFixture);
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
    await expect(page).toHaveScreenshot(`role-${width}-${zoom}x.png`, {
      fullPage: true,
      animations: "disabled",
    });
  }
});
