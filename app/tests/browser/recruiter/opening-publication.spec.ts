import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("FM3 legacy opening publication is confirmed, public and independently withdrawn", async ({
  page,
}, testInfo) => {
  const bootstrap = process.env.LOCAL_PUBLICATION_RECRUITER_BOOTSTRAP_URL;
  test.skip(
    !bootstrap,
    "Authenticated synthetic publication bootstrap required",
  );
  await page.goto(bootstrap!);
  const origin = new URL(page.url()).origin;
  const tenant = new URL(page.url()).pathname.split("/")[2];
  await page.goto(`${origin}/tenants/${tenant}/recruiter/organization/`);
  const csrf = await page.locator("[name=csrfmiddlewaretoken]").inputValue();
  const headers = { "X-Tenant-ID": tenant, "X-CSRFToken": csrf };
  const units = await page.request.get(
    `${origin}/api/v1/tenants/${tenant}/business-units`,
    { headers },
  );
  const unit = (await units.json())[0].id;
  const creation = await page.request.post(
    `${origin}/api/v1/tenants/${tenant}/openings`,
    {
      headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
      data: {
        business_unit_id: unit,
        title: "FM3 synthetic publication verification",
        description: "Synthetic public description only.",
        location: { display: "Bengaluru" },
        work_mode: "REMOTE",
        employment_type: "PERMANENT",
      },
    },
  );
  expect(creation.status()).toBe(201);
  const opening = await creation.json();
  await page.reload();
  const card = page.locator(`[data-opening-publication="${opening.id}"]`);
  await expect(
    card.getByText("Public publication: UNPUBLISHED", { exact: true }),
  ).toBeVisible();
  await card
    .getByRole("button", { name: "Open internally (does not publish)" })
    .click();
  await expect(
    card.getByText("Internal state: OPEN", { exact: true }),
  ).toBeVisible();
  await expect(
    card.getByRole("button", { name: "Publish", exact: true }),
  ).toBeDisabled();
  await card.getByRole("button", { name: "Preview", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(
    card.getByText("Synthetic public description only.", { exact: true }),
  ).toBeVisible();
  const publish = card.getByRole("button", { name: "Publish", exact: true });
  await publish.focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("dialog", { name: "Confirm public publication" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Cancel", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(publish).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Confirm publication", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    card.getByText("Public publication: PUBLISHED", { exact: true }),
  ).toBeVisible();
  const publicUrl = await card
    .getByRole("link", { name: "View public role" })
    .getAttribute("href");
  expect((await page.request.get(`${origin}/jobs/`)).status()).toBe(200);
  expect(await (await page.request.get(`${origin}/jobs/`)).text()).toContain(
    publicUrl!,
  );
  await card.getByRole("button", { name: "Preview", exact: true }).click();
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.locator("html").evaluate((el, factor) => {
      el.style.zoom = String(factor);
    }, zoom);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const audit = await new AxeBuilder({ page: page as never }).analyze();
    expect(
      audit.violations.filter((v) =>
        ["serious", "critical"].includes(v.impact ?? ""),
      ),
    ).toEqual([]);
    await card.screenshot({
      path: testInfo.outputPath(`publication-${width}-${zoom}x.png`),
    });
  }
  await page.locator("html").evaluate((el) => {
    el.style.zoom = "1";
  });
  // A concurrent source edit invalidates both the old publication and this preview.
  const managementPath = `${origin}/api/v1/tenants/${tenant}/openings/${opening.id}`;
  const latest = await (
    await page.request.get(`${managementPath}/publication`, { headers })
  ).json();
  const edit = await page.request.patch(managementPath, {
    headers: { ...headers, "If-Match": latest.source_etag },
    data: { description: "Freshly reviewed synthetic description." },
  });
  expect(edit.status()).toBe(200);
  await card
    .getByRole("button", { name: "Update publication", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm publication", exact: true })
    .click();
  await expect(card.getByRole("status")).toContainText(
    "opening or preview changed",
  );
  await card.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(
    card.getByText("Freshly reviewed synthetic description.", { exact: true }),
  ).toBeVisible();
  await card.getByRole("button", { name: "Publish", exact: true }).click();
  await page
    .getByRole("button", { name: "Confirm publication", exact: true })
    .click();
  await expect(
    card.getByText("Public publication: PUBLISHED", { exact: true }),
  ).toBeVisible();
  await card
    .getByRole("button", { name: "Withdraw publication", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm withdrawal", exact: true })
    .click();
  await expect(
    card.getByText("Public publication: UNPUBLISHED", { exact: true }),
  ).toBeVisible();
  await expect(
    card.getByText("Internal state: OPEN", { exact: true }),
  ).toBeVisible();
  expect(
    await (await page.request.get(`${origin}/jobs/`)).text(),
  ).not.toContain(publicUrl!);
  await page.reload();
  await expect(
    card.getByText("Public publication: UNPUBLISHED", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("[data-frontend-renderer=legacy]")).toBeVisible();
});
