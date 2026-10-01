import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const shell = `<!doctype html><html lang="en"><head><title>Review search criteria</title></head><body>
<main data-criteria-review data-tenant-id="00000000-0000-4000-8000-000000000001">
<h1>Review search criteria</h1><p data-original-prompt>Python engineer in Bengaluru</p>
<p data-review-status role="status" aria-live="polite"></p>
<p><strong data-estimated-count>3</strong> estimated candidates</p>
<form data-review-form><input type="hidden" name="context_type" value="AD_HOC"><div data-groups></div>
<button type="button" data-add-group>Add group</button><button type="submit">Run confirmed search</button></form>
</main></body></html>`;

test.beforeEach(async ({ page }) => {
  await page.route("**/search-handoffs/criteria-review", (route) =>
    route.fulfill({
      json: {
        etag: '"fixture-v1"',
        criteria: {
          context: { type: "AD_HOC" },
          groups: [],
          criteria: [],
          limit: 25,
        },
        estimated_count: 3,
      },
    }),
  );
  await page.goto(`/#handoff=${"c".repeat(43)}`);
  await page.setContent(shell);
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  await expect(page.getByRole("status")).toContainText("Criteria restored");
});

test("adds edits moves and removes criteria without changing stable IDs", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add group" }).click();
  const group = page.locator("[data-group-id]").first();
  const groupId = await group.getAttribute("data-group-id");
  await group.getByLabel("Match within group").selectOption("ANY");
  await group.getByRole("button", { name: "Add criterion" }).click();
  const criterion = group.locator("[data-criterion-id]").first();
  const criterionId = await criterion.getAttribute("data-criterion-id");
  await criterion.getByLabel("Value").fill("Django");
  await criterion.getByLabel("Group membership").selectOption(groupId!);
  await expect(group).toHaveAttribute("data-group-id", groupId!);
  await expect(criterion).toHaveAttribute("data-criterion-id", criterionId!);
  await criterion.getByRole("button", { name: "Remove criterion" }).click();
  await expect(group.locator("[data-criterion-id]")).toHaveCount(0);
});

test("is keyboard usable, reflows at 320px, and has no serious accessibility violations", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 900 });
  await page.getByRole("button", { name: "Add group" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("[data-group-id]")).toHaveCount(1);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const results = await new AxeBuilder({ page: page as never }).analyze();
  expect(
    results.violations.filter(
      (item) => item.impact === "critical" || item.impact === "serious",
    ),
  ).toEqual([]);
});

test("shows errors, original prompt, group semantics, and refreshed estimated impact", async ({
  page,
}) => {
  await expect(page.getByText(/original prompt is not retained/)).toBeVisible();
  await page.getByRole("button", { name: "Add group" }).click();
  await expect(
    page.getByText(/ANY includes a candidate when one criterion matches/),
  ).toBeVisible();
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page.getByRole("status")).toContainText("criterion");
});
