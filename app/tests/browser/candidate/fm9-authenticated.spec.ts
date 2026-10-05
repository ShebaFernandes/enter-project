import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("FM9 authenticated candidate edits, consents, publishes and keeps protected state ephemeral", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM9_BOOTSTRAP_URL", "candidate");
  test.skip(!bootstrap, "Requires an isolated FM9 flag-on verification server");

  await page.goto(bootstrap!);
  const origin = new URL(page.url()).origin;
  await page.goto(`${origin}/candidate/profile/`);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByRole("heading", { name: "Right person. Right problem." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Review my existing profile" })
    .click();
  await expect(page.getByLabel("Full name")).toHaveValue(
    "Synthetic Search Candidate",
  );
  await page.locator("summary").filter({ hasText: "Career history" }).click();
  await expect(
    page.getByRole("group", { name: "Employment record 1" }),
  ).toBeVisible();

  await page
    .getByLabel("Meaningful work")
    .fill("Synthetic FM9 profile verification.");
  await page.getByLabel("Notice period", { exact: true }).fill("30 days");
  const profileWrite = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/candidate/profile") &&
      response.request().method() === "PATCH",
  );
  const visibilityWrite = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/candidate/visibility") &&
      response.request().method() === "PUT",
  );
  await page
    .getByRole("button", { name: "Save profile and visibility" })
    .click();
  expect((await profileWrite).status()).toBe(200);
  expect((await visibilityWrite).status()).toBe(200);
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Profile and visibility saved" }),
  ).toBeVisible();

  const publication = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/candidate/profile/publish") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Publish profile" }).click();
  expect((await publication).status()).toBe(200);
  await expect(
    page.getByRole("status").filter({ hasText: "Profile publication saved" }),
  ).toBeVisible();

  expect(
    (await new AxeBuilder({ page: page as never }).analyze()).violations.filter(
      (item) => ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
