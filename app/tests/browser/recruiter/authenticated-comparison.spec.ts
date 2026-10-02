import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("authenticated recruiter compares two currently authorized search results", async ({
  page,
}) => {
  const bootstrapUrl = localBootstrap("LOCAL_RECRUITER_BOOTSTRAP_URL");
  test.skip(!bootstrapUrl, "Run with a one-time local synthetic recruiter URL");

  await page.goto(bootstrapUrl!);
  await expect(page.getByText("Signed in as recruiter")).toBeVisible();
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python engineers");
  await page.getByLabel("Value").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Synthetic Search Candidate" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Synthetic Comparison Candidate" }),
  ).toBeVisible();
  await page.getByLabel("Compare Synthetic Search Candidate").check();
  await page.getByLabel("Compare Synthetic Comparison Candidate").check();
  await page
    .getByRole("button", { name: "Compare selected candidates" })
    .click();
  await expect(page).toHaveURL(/\/recruiter\/comparison\/#handoff=/);
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
  await expect(
    page.getByRole("region", { name: "Side-by-side evidence" }),
  ).toContainText("provides no recommendation", { timeout: 10_000 });
});
