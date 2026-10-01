import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { localBootstrap } from "../local-bootstrap";

test("FM5 authenticated React review restores edits and confirms into legacy results", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM5_BOOTSTRAP_URL");
  test.skip(!bootstrap, "Requires FM5 flag-on synthetic verification server");
  await page.goto(bootstrap!);
  await page.getByLabel("Describe the candidate you need").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/criteria-review\/#handoff=/);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(page.getByRole("status")).toContainText("Criteria restored");
  await page.getByLabel("Match within group").selectOption("ANY");
  await expect(page.getByRole("status")).toContainText(
    "Estimated impact updated",
  );
  await page.reload();
  await expect(page.getByLabel("Match within group")).toHaveValue("ANY");
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
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `../docs/evidence/frontend-migration/fm5/review-live-${width}-${zoom}x.png`,
      fullPage: true,
    });
    expect(
      (
        await new AxeBuilder({ page: page as never }).analyze()
      ).violations.filter((v) =>
        ["serious", "critical"].includes(v.impact ?? ""),
      ),
    ).toEqual([]);
  }
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page).toHaveURL(/search\/\?view=results#handoff=/);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "legacy",
  );
  await page.getByLabel("Compare Synthetic Search Candidate").check();
  await page.getByLabel("Compare Synthetic Comparison Candidate").check();
  await page
    .getByRole("button", { name: "Compare selected candidates" })
    .click();
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Return to results" }).click();
  await expect(page).toHaveURL(/search\/\?view=results#handoff=/);
  await page.reload();
  await expect(
    page.getByLabel("Compare Synthetic Search Candidate"),
  ).toBeChecked();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
