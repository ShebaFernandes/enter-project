import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("FM6 real search review results detail selection comparison and safe return", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM6_BOOTSTRAP_URL");
  test.skip(!bootstrap, "Requires FM6 synthetic flag-on verification server");
  await page.goto(bootstrap!);
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python Bengaluru");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  await page.getByText("Applied criteria", { exact: true }).click();
  await expect(
    page.getByRole("group", { name: "Applied deterministic criteria" }),
  ).toContainText("Python");
  await page
    .getByRole("button", { name: "Adjust criteria", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText("Criteria restored");
  await page.getByLabel("Maximum results").fill("1");
  await expect(page.getByRole("dialog").getByRole("status")).toContainText(
    "Estimated impact updated",
  );
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(page.getByRole("article")).toHaveCount(1);
  const first = page.url();
  await page.getByRole("button", { name: "Load more" }).click();
  await expect(page.getByRole("article")).toHaveCount(2);
  await page.reload();
  await expect(page.getByRole("article")).toHaveCount(2);
  await page.goBack();
  await expect(page).toHaveURL(first);
  await expect(page.getByRole("article")).toHaveCount(1);
  await page.goForward();
  await expect(page.getByRole("article")).toHaveCount(2);
  await page
    .getByRole("button", { name: "View profile", exact: true })
    .first()
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "Synthetic Search Candidate",
  );
  await page.getByRole("button", { name: "Action", exact: true }).click();
  const management = await page
    .getByRole("link", { name: "Open resume sharing and candidate workspace" })
    .getAttribute("href");
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "View profile", exact: true }).first(),
  ).toBeFocused();
  await page.getByLabel("Compare Synthetic Search Candidate").check();
  await page.getByLabel("Compare Synthetic Comparison Candidate").check();
  await expect(page.getByRole("status")).toContainText("2 candidates selected");
  await page.reload();
  await expect(
    page.getByLabel("Compare Synthetic Search Candidate"),
  ).toBeChecked();
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.evaluate((value) => {
      document.documentElement.style.zoom = String(value);
    }, zoom);
    await page.screenshot({
      path: `../docs/evidence/frontend-migration/fm6/results-live-${width}-${zoom}x.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: /^Compare \(\d+\)$/ }).click();
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Return to results" }).click();
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByLabel("Compare Synthetic Search Candidate"),
  ).toBeChecked();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  await page.goto(new URL(management!, page.url()).href);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByLabel("Recruiter note", { exact: true }),
  ).toBeVisible();
});
