import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("authenticated legacy review results comparison refresh and return keep protected state out of storage", async ({
  page,
}) => {
  const bootstrap = process.env.LOCAL_FM4_BOOTSTRAP_URL;
  test.skip(
    !bootstrap,
    "Requires one-time existing synthetic recruiter bootstrap",
  );
  await page.goto(bootstrap!);
  await page.getByLabel("Describe the candidate you need").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/criteria-review\/#handoff=/);
  await expect(page.getByRole("status")).toContainText("Criteria restored");
  await page.reload();
  await expect(page.getByRole("status")).toContainText("Criteria restored");
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page).toHaveURL(/search\/\?view=results#handoff=/);
  await page.getByLabel("Compare Synthetic Search Candidate").check();
  await page.getByLabel("Compare Synthetic Comparison Candidate").check();
  await expect(
    page.getByText("2 candidates selected for comparison."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Compare selected candidates" })
    .click();
  await expect(page).toHaveURL(/comparison\/#handoff=/);
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  expect(
    await page.evaluate(() => ({
      local: { ...localStorage },
      session: { ...sessionStorage },
    })),
  ).toEqual({ local: {}, session: {} });
  const audit = await new AxeBuilder({ page: page as never }).analyze();
  expect(
    audit.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  await page.getByRole("button", { name: "Return to results" }).click();
  await expect(page).toHaveURL(/search\/\?view=results#handoff=/);
  await expect(
    page.getByLabel("Compare Synthetic Search Candidate"),
  ).toBeChecked();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).not.toHaveURL(/recruiter\/search/);
});
