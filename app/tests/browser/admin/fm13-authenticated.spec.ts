import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";

test("FM13 authenticated Tenant Admin reads redacted audit and starts an access review", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM13_BOOTSTRAP_URL", "tenant_admin");
  test.skip(
    !bootstrap,
    "Requires an isolated FM13 flag-on verification server",
  );

  await page.goto(bootstrap!);
  await expect(page.locator("body")).toHaveAttribute(
    "data-frontend-renderer",
    "react",
  );
  await expect(
    page.getByRole("heading", { name: "Tenant governance" }),
  ).toBeVisible();
  await expect(
    page.getByText(/does not grant access to candidate content/i),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Audit metadata" }).click();
  await expect(page.getByText(/This read was audited/i)).toBeVisible();
  await expect(page.getByText(/resume|email|phone/i)).toHaveCount(0);

  await page.getByRole("tab", { name: "Access reviews" }).click();
  const due = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 16);
  await page.getByLabel("Review type").selectOption("MEMBERSHIP");
  await page.getByLabel("Due date").fill(due);
  await page.getByRole("button", { name: "Start access review" }).click();
  await expect(page.getByText("Access review started.")).toBeVisible();
  await expect(
    page.getByRole("region", { name: "MEMBERSHIP access review" }).first(),
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
