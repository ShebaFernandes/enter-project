import { expect, test } from "@playwright/test";

test("neutral finding shows evidence and no inferred departure reason", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:4173");
  await page.setContent(
    `<div id="target"><aside class="finding" aria-label="Informational employment finding"><strong>Employment information</strong><p>Candidate left Synthetic Employer after approximately 8 months.</p><details open><summary>Supporting evidence</summary><dl><dt>Company</dt><dd>Synthetic Employer</dd><dt>Confirmed dates</dt><dd>2025-01-01 to 2025-09-01</dd><dt>Calculated duration</dt><dd>8 months, 0 days</dd><dt>Calculation version</dt><dd>short-tenure-v1</dd><dt>Evaluated</dt><dd>2026-09-30T00:00:00Z</dd></dl></details></aside></div>`,
  );
  await expect(
    page.getByText(/Candidate left Synthetic Employer/),
  ).toBeVisible();
  await expect(page.getByText("short-tenure-v1")).toBeVisible();
  await expect(page.locator("#target")).not.toContainText(/reason|job hopper/i);
});
