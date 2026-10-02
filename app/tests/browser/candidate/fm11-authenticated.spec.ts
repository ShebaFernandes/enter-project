import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("FM11 authenticated candidate submits, tracks and exercises an immediate privacy right", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM11_BOOTSTRAP_URL", "candidate");
  test.skip(
    !bootstrap,
    "Requires an isolated FM11 flag-on verification server",
  );

  await page.goto(bootstrap!);
  const origin = new URL(page.url()).origin;
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await page.getByLabel("Full name").fill("Synthetic Search Candidate");
  await page
    .getByLabel("Verified email")
    .fill("synthetic-candidate@example.test");
  await page.getByLabel(/I consent to use of my profile/).check();
  const submission = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/candidate/applications") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Apply" }).click();
  expect((await submission).status()).toBe(201);

  await page.goto(`${origin}/candidate/applications/`);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByRole("heading", { name: "Software Engineer" }).first(),
  ).toBeVisible();
  await expect(
    page.getByText("Applied", { exact: true }).first(),
  ).toBeVisible();

  await page.goto(`${origin}/candidate/rights/`);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  const request = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/candidate/rights-requests") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Access my data" }).click();
  expect((await request).status()).toBe(202);
  await expect(page.getByText("Completed immediately")).toBeVisible();
  expect(
    (await new AxeBuilder({ page: page as never }).analyze()).violations.filter(
      (item) => ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
