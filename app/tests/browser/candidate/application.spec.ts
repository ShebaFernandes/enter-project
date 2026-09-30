import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("public application validates, preserves preferences, and reflows", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.setContent(`<!doctype html><html lang="en"><head><title>Apply for Software Engineer</title></head><body>
    <main class="candidate-application-shell">
      <h1>Software Engineer</h1>
      <p>Bengaluru · Remote · Permanent</p>
      <p>After applying, you can track progress and control notification channels.</p>
      <form data-application-form>
        <label>Full name <input name="full_name" required /></label>
        <label>Email <input name="email" type="email" required /></label>
        <label>Resume <input name="resume" type="file" required /></label>
        <label><input name="email_updates" type="checkbox" /> Email updates</label>
        <label><input name="whatsapp_updates" type="checkbox" /> WhatsApp updates</label>
        <label><input name="consent" type="checkbox" required /> I consent to this application</label>
        <button>Apply</button>
        <p role="status" aria-live="polite"></p>
      </form>
    </main></body></html>
  `);
  await page.addStyleTag({
    content:
      ".candidate-application-shell{max-width:48rem;margin:auto;padding:1rem}label{display:block;margin:.75rem 0}input{max-width:100%}",
  });

  await page.getByRole("button", { name: "Apply" }).click();
  await expect(page.getByLabel("Full name")).toBeFocused();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth),
  ).toBeLessThanOrEqual(320);
  const results = await new AxeBuilder({ page: page as never }).analyze();
  expect(
    results.violations.filter((item) => item.impact === "serious"),
  ).toEqual([]);
});

test("progress presents eight statuses and candidate-safe delivery states", async ({
  page,
}) => {
  const statuses = [
    "Applied",
    "Profile viewed",
    "Shortlisted",
    "Recruiter interested",
    "Interview requested",
    "Offer made",
    "Not selected",
    "Withdrawn",
  ];
  await page.setContent(`
    <main><h1>Your applications</h1>
      <ol aria-label="Application progress">${statuses.map((status) => `<li>${status}</li>`).join("")}</ol>
      <label><input type="checkbox" checked /> Email updates</label>
      <label><input type="checkbox" /> WhatsApp updates</label>
      <p>Delivery: Pending</p><p>Delivery: Sent</p><p>Delivery: Failed</p><p>Delivery: Cancelled</p>
    </main>
  `);
  for (const status of statuses) {
    await expect(page.getByText(status, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("SENDING")).toHaveCount(0);
});
