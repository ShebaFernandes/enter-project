import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { localBootstrap } from "../local-bootstrap";

test("FM7 authenticated search, candidate work, stale write, refresh and rollback-safe navigation", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM7_BOOTSTRAP_URL");
  test.skip(!bootstrap, "Requires an isolated FM7 flag-on verification server");
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto(bootstrap!);
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Python engineer in Bengaluru with at least 5 years experience");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  await page
    .getByRole("article")
    .filter({
      has: page.getByRole("heading", {
        name: "Synthetic Search Candidate",
        exact: true,
      }),
    })
    .getByRole("button", { name: "View profile", exact: true })
    .click();
  await page.getByRole("button", { name: "Action", exact: true }).click();
  await page
    .getByRole("link", { name: "Open resume sharing and candidate workspace" })
    .click();
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByLabel("Recruiter note", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "This information does not change eligibility, score, rank or hiring status.",
    ),
  ).toBeVisible();
  const note = `Synthetic FM7 note ${Date.now()}`;
  await page.getByLabel("Recruiter note", { exact: true }).fill(note);
  await page.getByRole("button", { name: "Save note", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Note saved");
  await expect(page.getByText(note, { exact: true })).toBeVisible();
  await page.getByLabel("Shortlisted", { exact: true }).check();
  await page.getByRole("button", { name: "Save internal status" }).click();
  await expect(page.getByRole("status")).toContainText("Internal status saved");
  await page.reload();
  await expect(page.getByLabel("Shortlisted", { exact: true })).toBeChecked();
  const other = await page.context().newPage();
  await other.goto(page.url());
  await expect(
    other.getByLabel("Internal status", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Internal status", { exact: true })
    .selectOption("CONTACTED");
  await page.getByRole("button", { name: "Save internal status" }).click();
  await expect(page.getByRole("status")).toContainText("Internal status saved");
  await other
    .getByLabel("Internal status", { exact: true })
    .selectOption("SCREENING");
  await other.getByRole("button", { name: "Save internal status" }).click();
  await expect(
    other.getByRole("region", { name: "Resolve changed information" }),
  ).toBeVisible();
  await other.close({ runBeforeUnload: false });
  await page.reload();
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
    await expect(
      page.getByLabel("Recruiter note", { exact: true }),
    ).toBeVisible();
    expect(
      (
        await new AxeBuilder({ page: page as never }).analyze()
      ).violations.filter((v) =>
        ["serious", "critical"].includes(v.impact ?? ""),
      ),
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `../docs/evidence/frontend-migration/fm7/management-live-${width}-${zoom}x.png`,
      fullPage: true,
    });
  }
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  await page.getByRole("link", { name: "Return to search" }).click();
  await expect(
    page.getByLabel("Describe the candidate you need"),
  ).toBeVisible();
  await page.goBack();
  await expect(
    page.getByLabel("Recruiter note", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/^http:\/\/127\.0\.0\.1:\d+\/$/);
  await page.goBack();
  await expect(page.getByLabel("Recruiter note", { exact: true })).toHaveCount(
    0,
  );
});
