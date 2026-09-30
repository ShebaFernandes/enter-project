import { expect, test } from "@playwright/test";

test("authenticated local recruiter searches, views evidence, and signs out safely", async ({
  page,
}) => {
  const bootstrapUrl = process.env.LOCAL_RECRUITER_BOOTSTRAP_URL;
  test.skip(!bootstrapUrl, "Run with a one-time local synthetic recruiter URL");

  await page.goto(bootstrapUrl!);
  await expect(page.getByText("Signed in as recruiter")).toBeVisible();
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Maybe an engineer");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/criteria-review/);
  await expect(page.getByText("Maybe an engineer")).toBeVisible();
  await expect(page.getByText(/estimated candidates in scope/)).toBeVisible();
  await page.getByLabel("Match within group").selectOption("ANY");
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page).toHaveURL(/recruiter\/search\/$/);
  await expect(page.locator(".search-status")).toContainText(
    "confirmed result",
  );
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python engineer in Bengaluru");
  await page.getByLabel("Value").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Synthetic Search Candidate")).toBeVisible();
  await expect(
    page.getByText(
      "Candidate left Synthetic Previous Employer after approximately 8 months.",
    ),
  ).toBeVisible();

  await page.getByRole("button", { name: "View authorized details" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText(
    "Synthetic Previous Employer",
  );
  await page.getByRole("button", { name: "Close" }).click();

  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ status: 200, body: "Signed out" }),
  );
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/api\/v1\/auth\/login/);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);

  await page.goBack();
  await expect(page.getByText("Signed in as recruiter")).toHaveCount(0);
});
