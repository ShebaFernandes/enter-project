import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("local synthetic profile matches the full engineer query with authorized detail", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM6_BOOTSTRAP_URL");
  test.skip(
    !bootstrap,
    "Requires synthetic local recruiter server with search/results flags",
  );
  await page.goto(bootstrap!);
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python engineer in Bengaluru with at least 5 years experience");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  const candidate = page.getByRole("article").filter({
    has: page.getByRole("heading", {
      name: "Synthetic Search Candidate",
      exact: true,
    }),
  });
  await expect(candidate).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Applied deterministic criteria" }),
  ).toContainText("engineer");
  await expect(candidate).toContainText(
    "does not change eligibility, score, rank or hiring status",
  );
  await candidate
    .getByRole("button", { name: "View authorized details" })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Current authorized candidate details loaded",
  );
  await expect(page.getByRole("dialog")).toContainText(
    "Synthetic Search Candidate",
  );
  await page.screenshot({
    path: "../docs/evidence/frontend-migration/fm6/local-discovery-detail.png",
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(candidate).toBeVisible();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
