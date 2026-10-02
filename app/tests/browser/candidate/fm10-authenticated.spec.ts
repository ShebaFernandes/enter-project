import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("FM10 authenticated candidate reads a public role and submits once", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM10_BOOTSTRAP_URL", "candidate");
  test.skip(
    !bootstrap,
    "Requires an isolated FM10 flag-on verification server",
  );

  await page.goto(bootstrap!);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByRole("heading", { name: "Software Engineer" }),
  ).toBeVisible();
  await page.getByLabel("Full name").fill("Synthetic Search Candidate");
  await page
    .getByLabel("Verified email")
    .fill("synthetic-candidate@example.test");
  await page
    .getByLabel("Why are you interested?")
    .fill("Synthetic FM10 application verification.");
  await page.getByRole("checkbox", { name: "Email", exact: true }).check();
  await page.getByLabel(/I consent to use of my profile/).check();
  const submission = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/candidate/applications") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Apply" }).click();
  expect((await submission).status()).toBe(201);
  await expect(page.getByRole("status")).toContainText("Application submitted");
  expect(
    (await new AxeBuilder({ page: page as never }).analyze()).violations.filter(
      (item) => ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
