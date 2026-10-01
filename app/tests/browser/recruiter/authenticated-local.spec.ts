import { expect, test } from "@playwright/test";

test("authenticated local recruiter searches, views evidence, and signs out safely", async ({
  page,
}) => {
  const bootstrapUrl = process.env.LOCAL_RECRUITER_BOOTSTRAP_URL;
  test.skip(!bootstrapUrl, "Run with a one-time local synthetic recruiter URL");

  await page.goto(bootstrapUrl!);
  await expect(page.getByText("Signed in as recruiter")).toBeVisible();
  page.on("dialog", (dialog) => dialog.accept());
  await page
    .getByLabel("Describe the candidate you need")
    .fill("Maybe an engineer");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/criteria-review/);
  await expect(page.getByText("Maybe an engineer")).toBeVisible();
  await expect(page.getByText(/estimated candidates in scope/)).toBeVisible();
  await page.getByLabel("Match within group").selectOption("ANY");
  const tenantId = await page
    .locator("[data-criteria-review]")
    .getAttribute("data-tenant-id");
  expect(tenantId).not.toBeNull();
  const confirmed = await page.evaluate(async (activeTenantId) => {
    const reviewed = JSON.parse(
      sessionStorage.getItem("enter.criteria-review.v1") ?? "null",
    ) as { criteria: unknown } | null;
    const csrf = (
      document.querySelector("[name=csrfmiddlewaretoken]") as HTMLInputElement
    ).value;
    const response = await fetch(`/api/v1/tenants/${activeTenantId}/searches`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf,
        "X-Tenant-ID": activeTenantId!,
      },
      credentials: "same-origin",
      body: JSON.stringify(reviewed!.criteria),
    });
    const body = (await response.json()) as Record<string, unknown>;
    sessionStorage.setItem("enter.confirmed-search.v1", JSON.stringify(body));
    return { ok: response.ok, body };
  }, tenantId);
  expect(confirmed.ok).toBe(true);
  const resultPage = await page.context().newPage();
  const resultsUrl = `${new URL(page.url()).origin}/tenants/${tenantId}/recruiter/search/`;
  await resultPage.goto(resultsUrl);
  await resultPage.evaluate((result) => {
    sessionStorage.setItem("enter.confirmed-search.v1", JSON.stringify(result));
  }, confirmed.body);
  await resultPage.reload();
  await page.close({ runBeforeUnload: false });
  await expect(resultPage.locator(".search-status")).toContainText(
    "confirmed result",
  );
  await resultPage
    .getByLabel("Describe the candidate you need")
    .fill("Python engineer in Bengaluru");
  await resultPage.getByLabel("Value").fill("Python");
  await resultPage.getByRole("button", { name: "Search", exact: true }).click();
  await expect(
    resultPage.getByRole("heading", { name: "Synthetic Search Candidate" }),
  ).toBeVisible();
  await expect(
    resultPage.getByText(
      "Candidate left Synthetic Previous Employer after approximately 8 months.",
    ),
  ).toBeVisible();

  await resultPage
    .getByRole("article")
    .filter({
      has: resultPage.getByRole("heading", {
        name: "Synthetic Search Candidate",
        exact: true,
      }),
    })
    .getByRole("button", { name: "View authorized details" })
    .click();
  await expect(resultPage.getByRole("dialog")).toBeVisible();
  await expect(resultPage.getByRole("dialog")).toContainText(
    "Synthetic Previous Employer",
  );
  await resultPage.getByRole("button", { name: "Close" }).click();

  await resultPage.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ status: 200, body: "Signed out" }),
  );
  await resultPage.getByRole("button", { name: "Sign out" }).click();
  await expect(resultPage).toHaveURL(/api\/v1\/auth\/login/);
  expect(await resultPage.evaluate(() => sessionStorage.length)).toBe(0);

  await resultPage.goBack();
  await expect(resultPage.getByText("Signed in as recruiter")).toHaveCount(0);
});
