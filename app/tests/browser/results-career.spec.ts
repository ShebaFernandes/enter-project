import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import AxeBuilder from "@axe-core/playwright";
test("result career journey shows company details on hover and focus at desktop and mobile", async ({
  page,
  browser,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.route("**/api/v1/session", (route) => route.fulfill({ json: {} }));
  await page.route("**/search-handoffs/search-results", (route) =>
    route.fulfill({ json: { search_id: "search" } }),
  );
  await page.route("**/search-handoffs/search-results/display", (route) =>
    route.fulfill({
      json: {
        search_id: "search",
        next_cursor: null,
        items: [
          {
            candidate_id: "candidate",
            summary: {
              name: "Arjun Nair",
              current_role: "Senior Backend Engineer",
              current_company: "Google",
              location: "Bengaluru",
              experience_years: "5.6",
              notice_period: "30 days",
              skills: [
                "Java",
                "Spring Boot",
                "Kafka",
                "Microservices",
                "PostgreSQL",
                "AWS",
              ],
              employment_history: [
                {
                  company: "Amazon",
                  role_title: "Software Engineer",
                  start_date: "2019-01-01",
                  end_date: "2020-01-01",
                },
                {
                  company: "Razorpay",
                  role_title: "Backend Engineer",
                  start_date: "2020-01-01",
                  end_date: "2022-01-01",
                },
                {
                  company: "Google",
                  role_title: "Senior Backend Engineer",
                  start_date: "2023-01-01",
                  end_date: null,
                  is_current: true,
                },
              ],
            },
            findings: [
              {
                code: "SHORT_TENURE",
                informational_only: true,
                message:
                  "Candidate left Synthetic Previous Employer after approximately 8 months.",
                evidence: {
                  employment_record_id: "00000000-0000-4000-8000-000000000001",
                  company: "Synthetic Previous Employer",
                  confirmed_start_date: "2019-01-01",
                  confirmed_end_date: "2019-09-01",
                  calculated_duration: {
                    calendar_months: 8,
                    remaining_days: 0,
                  },
                  calculation_version: "short-tenure-v1",
                  evaluated_at: "2026-10-01T00:00:00Z",
                },
              },
              {
                code: "SHORT_TENURE",
                informational_only: true,
                message:
                  "Candidate left Synthetic Previous Employer after approximately 8 months.",
                evidence: {
                  employment_record_id: "00000000-0000-4000-8000-000000000002",
                  company: "Synthetic Previous Employer",
                  confirmed_start_date: "2020-01-01",
                  confirmed_end_date: "2020-09-01",
                  calculated_duration: {
                    calendar_months: 8,
                    remaining_days: 0,
                  },
                  calculation_version: "short-tenure-v1",
                  evaluated_at: "2026-10-01T00:00:00Z",
                },
              },
            ],
            evidence: [],
            unknowns: [],
          },
        ],
      },
    }),
  );
  await page.goto(
    `/app/tests/browser/fixtures/fm6.html#handoff=${"a".repeat(43)}`,
  );
  await expect(
    page.getByRole("img", { name: "enter", exact: true }),
  ).toBeVisible();
  expect(
    await page
      .getByRole("img", { name: "enter", exact: true })
      .evaluate((element) => (element as HTMLImageElement).naturalWidth),
  ).toBe(1400);
  await expect(
    page.getByRole("heading", { name: "Showing 1 of 1 results" }),
  ).toBeVisible();
  await expect(page.getByText(/2 separate employment records/)).toHaveCount(1);
  await page.getByRole("button", { name: "Razorpay", exact: true }).hover();
  await expect(page.getByRole("tooltip")).toContainText(
    "Backend Engineer at Razorpay",
  );
  await expect(page.getByRole("tooltip")).toContainText(
    "2020-01-01 – 2022-01-01",
  );
  await page.mouse.move(0, 0);
  await page.getByRole("button", { name: "Amazon", exact: true }).focus();
  await expect(page.getByRole("tooltip")).toContainText(
    "Software Engineer at Amazon",
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  expect(
    (
      await new AxeBuilder({
        page: page as unknown as ConstructorParameters<
          typeof AxeBuilder
        >[0]["page"],
      }).analyze()
    ).violations,
  ).toEqual([]);
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(() => document.fonts.check('800 15px "Results Inter"')),
  ).toBe(true);
  await page.getByRole("heading", { name: "Showing 1 of 1 results" }).click();
  await page.screenshot({ path: "/tmp/results-desktop.png", fullPage: true });
  const reference = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const ref = await reference.newPage();
  const fontCss = [400, 500, 600, 700, 800]
    .map(
      (weight) =>
        `@font-face { font-family: Inter; font-weight:${weight}; src:url(http://127.0.0.1:4173/app/frontend/react/assets/inter-${weight}.ttf); }`,
    )
    .join("\n");
  await ref.route("https://fonts.googleapis.com/**", (route) =>
    route.fulfill({ contentType: "text/css", body: fontCss }),
  );
  await ref.route("**/results-reference.html", async (route) =>
    route.fulfill({
      contentType: "text/html",
      body: await readFile(
        "../enter_recruiter_recruiter_candidate_ux.html",
        "utf8",
      ),
    }),
  );
  await ref.goto("/results-reference.html");
  await ref.locator("#recruiterEmail").fill("recruiter@synthetic.example");
  await ref.locator(".primary-choice").click();
  await ref.locator("#searchInput").fill("Java");
  await ref.locator("#searchBtn").click();
  await expect(ref.locator("#results")).toBeVisible();
  await ref.evaluate(() => document.fonts.ready);
  await ref.screenshot({ path: "/tmp/results-reference.png", fullPage: true });
  const referenceCard = await ref.locator(".card").first().boundingBox();
  const actualCard = await page.locator(".result-card").first().boundingBox();
  // Results retain the compact width of the supplied reference.
  expect(referenceCard?.width).toBe(900);
  expect(actualCard?.width).toBe(referenceCard?.width);
  expect(actualCard?.x).toBeGreaterThanOrEqual(0);
  expect((actualCard?.x ?? 0) + (actualCard?.width ?? 0)).toBeLessThanOrEqual(
    1440,
  );
  const actualAvatar = await page.locator(".candidate-avatar").boundingBox();
  const referenceAvatar = await ref
    .locator(".candidate-avatar")
    .first()
    .boundingBox();
  expect(actualAvatar?.width).toBe(referenceAvatar?.width);
  await reference.close();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Google", exact: true }).click();
  await expect(page.getByRole("tooltip")).toContainText("Present");
  await expect(page.getByRole("tooltip")).toHaveCSS(
    "background-color",
    "rgb(17, 19, 66)",
  );
  const tooltipBox = await page.getByRole("tooltip").boundingBox();
  expect(tooltipBox?.x).toBeGreaterThanOrEqual(0);
  expect((tooltipBox?.x ?? 0) + (tooltipBox?.width ?? 0)).toBeLessThanOrEqual(
    390,
  );
  await page.screenshot({ path: "/tmp/results-mobile.png", fullPage: true });
});
