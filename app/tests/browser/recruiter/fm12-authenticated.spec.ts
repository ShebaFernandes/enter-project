import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("FM12 authenticated recruiter manages tenant-scoped organization data", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM12_BOOTSTRAP_URL");
  test.skip(
    !bootstrap,
    "Requires an isolated FM12 flag-on verification server",
  );

  await page.goto(bootstrap!);
  const authenticatedUrl = new URL(page.url());
  const tenantId = authenticatedUrl.pathname.split("/")[2];
  await page.goto(
    new URL(
      `/tenants/${tenantId}/recruiter/organization/`,
      authenticatedUrl.origin,
    ).href,
  );

  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByRole("heading", { name: "Hiring organization" }),
  ).toBeVisible();
  await expect(
    page.getByText(/never merge with candidate-controlled profiles/i),
  ).toBeVisible();

  const suffix = Date.now();
  const unitName = `Synthetic FM12 unit ${suffix}`;
  await page.getByLabel("Business unit name").fill(unitName);
  await page
    .getByLabel("Description (optional)")
    .first()
    .fill("FM12 verification only");
  await page.getByRole("button", { name: "Create business unit" }).click();
  await expect(
    page.getByText("Business unit created.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".fm12-list strong").filter({ hasText: unitName }),
  ).toBeVisible();

  const syntheticName = `Synthetic FM12 candidate ${suffix}`;
  await page.getByLabel("Synthetic display name").fill(syntheticName);
  await page.getByLabel("Synthetic location").fill("Bengaluru");
  await page.getByLabel("Experience years").fill("4.5");
  await page.getByLabel("Synthetic skills").fill("Python, PostgreSQL");
  await page.getByLabel(/I confirm this is entirely synthetic/).check();
  await page
    .getByRole("button", { name: "Create synthetic candidate" })
    .click();
  await expect(
    page.getByText("Synthetic candidate created with immutable provenance.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.locator(".fm12-list strong").filter({ hasText: syntheticName }),
  ).toBeVisible();
  await expect(
    page.getByText("Recruiter-entered synthetic record").last(),
  ).toBeVisible();

  expect(
    (await new AxeBuilder({ page: page as never }).analyze()).violations.filter(
      (item) => ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
