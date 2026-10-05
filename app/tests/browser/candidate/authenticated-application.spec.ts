import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("authenticated candidate applies, recruiter publishes, candidate tracks and signs out safely", async ({
  browser,
}) => {
  const candidateBootstrap = localBootstrap(
    "LOCAL_CANDIDATE_BOOTSTRAP_URL",
    "candidate",
  );
  // Use a dedicated one-time recruiter bootstrap because the full suite also
  // verifies the recruiter search journey in parallel.
  const recruiterBootstrap = localBootstrap(
    "LOCAL_APPLICATION_RECRUITER_BOOTSTRAP_URL",
  );
  test.skip(
    !candidateBootstrap || !recruiterBootstrap,
    "Run with one-time local synthetic candidate and recruiter URLs",
  );

  const candidateContext = await browser.newContext();
  const candidatePage = await candidateContext.newPage();
  await candidatePage.goto(candidateBootstrap!);
  await expect(candidatePage.getByRole("heading", { level: 1 })).toHaveText(
    "Software Engineer",
  );
  await candidatePage.getByLabel("Full name").fill("Synthetic Candidate");
  await candidatePage
    .getByLabel("Verified email")
    .fill("candidate@local-synthetic.invalid");
  await candidatePage.getByLabel("Email", { exact: true }).check();
  await candidatePage
    .getByLabel(
      "I consent to use of my profile and clean resume for this application.",
      { exact: true },
    )
    .check();
  const submissionResponse = candidatePage.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/candidate/applications") &&
      response.request().method() === "POST",
  );
  await candidatePage.getByRole("button", { name: "Apply" }).click();
  const submitted = await submissionResponse;
  expect(submitted.status()).toBe(201);
  const application = (await submitted.json()) as { id: string };
  const submittedEtag = submitted.headers()["etag"];
  await expect(candidatePage.getByRole("status")).toContainText(
    "Application submitted",
  );

  const recruiterContext = await browser.newContext();
  const recruiterPage = await recruiterContext.newPage();
  await recruiterPage.goto(recruiterBootstrap!);
  const applicationOrigin = new URL(recruiterPage.url()).origin;
  const tenantMatch = recruiterPage.url().match(/\/tenants\/([^/]+)\//);
  expect(tenantMatch).not.toBeNull();
  const tenantId = tenantMatch![1];
  const csrf = await recruiterPage
    .locator("[name=csrfmiddlewaretoken]")
    .inputValue();
  const preview = await recruiterContext.request.post(
    `${applicationOrigin}/api/v1/tenants/${tenantId}/applications/${application.id}/status-preview`,
    {
      data: { internal_status: "SHORTLISTED" },
      headers: {
        "X-Tenant-ID": tenantId,
        "If-Match": submittedEtag,
        "X-CSRFToken": csrf,
      },
    },
  );
  expect(preview.status()).toBe(200);
  const previewBody = (await preview.json()) as { preview_id: string };
  const publish = await recruiterContext.request.post(
    `${applicationOrigin}/api/v1/tenants/${tenantId}/applications/${application.id}/status-publish`,
    {
      data: {
        preview_id: previewBody.preview_id,
        candidate_status: "SHORTLISTED",
        confirm: true,
        notify_channels: ["EMAIL"],
      },
      headers: {
        "X-Tenant-ID": tenantId,
        "If-Match": preview.headers()["etag"],
        "Idempotency-Key": crypto.randomUUID(),
        "X-CSRFToken": csrf,
      },
    },
  );
  expect(publish.status()).toBe(202);

  await candidatePage.goto(`${applicationOrigin}/candidate/applications/`);
  const applicationCard = candidatePage.locator(
    `[data-application-id="${application.id}"]`,
  );
  await expect(
    applicationCard.getByText("Shortlisted", { exact: true }),
  ).toBeVisible();
  await expect(applicationCard.getByText("EMAIL: pending")).toBeVisible();
  await candidatePage.getByRole("button", { name: "Sign out" }).click();
  await expect(candidatePage).toHaveURL(/^http:\/\/127\.0\.0\.1:\d+\/$/);
  expect(await candidatePage.evaluate(() => sessionStorage.length)).toBe(0);
  const protectedResponse = await candidateContext.request.get(
    `${applicationOrigin}/api/v1/candidate/applications`,
  );
  expect(protectedResponse.status()).toBe(403);

  await candidateContext.close();
  await recruiterContext.close();
});
