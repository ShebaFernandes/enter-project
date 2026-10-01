import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("authenticated Tenant Admin sees redacted governance without candidate content", async ({
  page,
}) => {
  const bootstrap = localBootstrap(
    "LOCAL_TENANT_ADMIN_BOOTSTRAP_URL",
    "tenant_admin",
  );
  test.skip(!bootstrap, "LOCAL_TENANT_ADMIN_BOOTSTRAP_URL is required");
  await page.goto(bootstrap!);
  await expect(
    page.getByRole("heading", { name: "Tenant governance" }),
  ).toBeVisible();
  await expect(
    page.getByText("Candidate content is not available"),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Audit metadata" }).click();
  await expect(page.getByText(/AUDIT_READ|Reading this history/)).toBeVisible();
});

test("authenticated recruiter opens synthetic organization management", async ({
  page,
}) => {
  const bootstrap = localBootstrap(
    "LOCAL_ORGANIZATION_RECRUITER_BOOTSTRAP_URL",
  );
  test.skip(
    !bootstrap,
    "LOCAL_ORGANIZATION_RECRUITER_BOOTSTRAP_URL is required",
  );
  const backendOrigin = new URL(bootstrap!).origin;
  await page.goto(bootstrap!);
  const tenantId = new URL(page.url()).pathname.split("/")[2];
  await page.goto(
    `${backendOrigin}/tenants/${tenantId}/recruiter/organization/`,
  );
  await expect(
    page.getByRole("heading", { name: "Hiring organization" }),
  ).toBeVisible();
  await expect(
    page.getByText("Recruiter-entered synthetic record"),
  ).toBeVisible();
});
