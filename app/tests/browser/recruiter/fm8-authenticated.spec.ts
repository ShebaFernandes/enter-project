import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { openInternalReview } from "../internal-review";
import { localBootstrap } from "../local-bootstrap";

test("FM8 authenticated React search comparison reauthorizes, removes and returns", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM8_BOOTSTRAP_URL");
  test.skip(!bootstrap, "Requires an isolated FM8 flag-on verification server");

  await page.goto(bootstrap!);
  await openInternalReview(page);
  await expect(page.getByRole("status")).toContainText("Criteria restored");
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  await page.getByLabel("Compare Synthetic Search Candidate").check();
  await page.getByLabel("Compare Synthetic Comparison Candidate").check();
  await page.getByRole("button", { name: /^Compare \(\d+\)$/ }).click();

  await expect(page).toHaveURL(/\/recruiter\/comparison\/#handoff=/);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByRole("status").filter({
      hasText: "2 currently authorized candidates loaded.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Synthetic Search Candidate" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Synthetic Comparison Candidate" }),
  ).toBeVisible();
  await expect(page.getByText(/provides no recommendation/)).toBeVisible();
  await expect(
    page.getByText(/does not affect ordering or scores/),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page: page as never }).analyze()).violations.filter(
      (item) => ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);

  await page
    .getByRole("button", { name: "Remove Synthetic Search Candidate" })
    .click();
  await expect(
    page.getByRole("button", { name: "Remove Synthetic Comparison Candidate" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Return to results" }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  await expect(
    page.getByRole("heading", { name: "Search results", exact: true }),
  ).toBeVisible();
});
