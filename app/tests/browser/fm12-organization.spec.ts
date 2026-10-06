import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const fixture = "/app/tests/browser/fixtures/fm12.html";
const tenant = "00000000-0000-4000-8000-000000000001";
const unitId = "00000000-0000-4000-8000-000000000121";
const openingId = "00000000-0000-4000-8000-000000000122";
const searchId = "00000000-0000-4000-8000-000000000123";
const base = `/api/v1/tenants/${tenant}`;
const unit = {
  id: unitId,
  name: "Engineering",
  description: "Synthetic unit",
  status: "ACTIVE",
  version: 1,
};
const opening = {
  id: openingId,
  business_unit_id: unitId,
  title: "Platform Engineer",
  location: { display: "Bengaluru" },
  work_mode: "HYBRID",
  employment_type: "PERMANENT",
  description: "Build a synthetic platform.",
  hiring_team_ids: [],
  state: "OPEN",
  version: 1,
};
const synthetic = {
  id: "00000000-0000-4000-8000-000000000124",
  display_name: "Synthetic Candidate",
  location: { display: "Pune" },
  experience_years: "4.25",
  skills: ["Python"],
  source_type: "RECRUITER_ENTERED_SYNTHETIC",
  source_label: "Recruiter-entered synthetic record",
  version: 1,
};
const saved = {
  id: "00000000-0000-4000-8000-000000000125",
  name: "Platform search",
  search_id: searchId,
  criteria: { context: { type: "OPENING", opening_id: openingId } },
  changed_since_save: [],
  version: 1,
};
const publication = {
  internal_state: "OPEN",
  publication_state: "UNPUBLISHED",
  public_fields: {
    title: opening.title,
    description: opening.description,
    location: "Bengaluru",
    work_mode: "HYBRID",
    employment_type: "PERMANENT",
    published_at: null,
  },
  public_url: null,
  source_etag: '"opening-v1"',
  preview_digest: "a".repeat(64),
};

async function mockReads(page: Page) {
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ json: { authenticated: true } }),
  );
  await page.route(`**${base}/business-units`, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: [unit] })
      : route.fallback(),
  );
  await page.route(`**${base}/openings`, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: [opening] })
      : route.fallback(),
  );
  await page.route(`**${base}/recruiter-entered-candidates`, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: [synthetic] })
      : route.fallback(),
  );
  await page.route(`**${base}/saved-searches`, (route) =>
    route.request().method() === "GET"
      ? route.fulfill({ json: [saved] })
      : route.fallback(),
  );
  await page.route(`**${base}/openings/${openingId}/publication`, (route) =>
    route.fulfill({
      headers: { ETag: publication.source_etag },
      json: publication,
    }),
  );
}

async function mockEmptyReads(page: Page) {
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ json: { authenticated: true } }),
  );
  for (const endpoint of [
    "business-units",
    "openings",
    "recruiter-entered-candidates",
    "saved-searches",
  ]) {
    await page.route(`**${base}/${endpoint}`, (route) =>
      route.fulfill({ json: [] }),
    );
  }
}

test("FM12 empty organization uses decorative setup artwork", async ({
  page,
}) => {
  await mockEmptyReads(page);
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Organization is ready" }),
  ).toBeVisible();
  const illustration = page.locator(".ui-empty-illustration");
  await expect(illustration).toHaveAttribute("alt", "");
  await expect(illustration).toHaveAttribute("aria-hidden", "true");
  expect(
    await illustration.evaluate(
      (image) => (image as HTMLImageElement).naturalWidth,
    ),
  ).toBe(1024);
});

test("FM12 loads tenant organization with immutable synthetic provenance and no browser storage", async ({
  page,
}) => {
  await mockReads(page);
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Hiring organization" }),
  ).toBeVisible();
  await expect(
    page.getByText("Recruiter-entered synthetic record"),
  ).toBeVisible();
  await expect(
    page.getByText(/never merge with candidate-controlled profiles/i),
  ).toBeVisible();
  await expect(
    page.getByText("Platform search", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM12 creates units, openings, synthetic fixtures and saved searches with protected requests", async ({
  page,
}) => {
  await mockReads(page);
  const writes: Record<string, unknown>[] = [];
  for (const path of [
    "business-units",
    "openings",
    "recruiter-entered-candidates",
    "saved-searches",
  ])
    await page.route(`**${base}/${path}`, async (route) => {
      if (route.request().method() === "GET") return route.fallback();
      expect(route.request().headers()["x-tenant-id"]).toBe(tenant);
      expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
      expect(route.request().headers()["idempotency-key"]).toBeTruthy();
      writes.push(route.request().postDataJSON());
      await route.fulfill({ status: 201, json: {} });
    });
  await page.goto(fixture);
  await page.getByLabel("Business unit name").fill("Synthetic Operations");
  await page.getByRole("button", { name: "Create business unit" }).click();
  await expect(page.getByText("Business unit created.")).toBeVisible();
  await page.getByLabel("Business unit", { exact: true }).selectOption(unitId);
  await page.getByLabel("Opening title").fill("Synthetic Reliability Engineer");
  await page.getByLabel("Location", { exact: true }).fill("Mumbai");
  await page.getByRole("button", { name: "Create opening" }).click();
  await expect(
    page.getByText("Opening created as an internal draft."),
  ).toBeVisible();
  await page.getByLabel("Synthetic display name").fill("Synthetic Person");
  await page.getByLabel("Synthetic location").fill("Pune");
  await page.getByLabel("Experience years").fill("3.5");
  await page.getByLabel("Synthetic skills").fill("Python, PostgreSQL");
  await page.getByLabel(/I confirm this is entirely synthetic/).check();
  await page
    .getByRole("button", { name: "Create synthetic candidate" })
    .click();
  await expect(
    page.getByText("Synthetic candidate created with immutable provenance."),
  ).toBeVisible();
  await page.getByLabel("Saved-search name").fill("Reliability candidates");
  await page.getByLabel("Owned search ID").fill(searchId);
  await page.getByRole("button", { name: "Save search" }).click();
  await expect(
    page.getByText("Search saved from its authoritative criteria context."),
  ).toBeVisible();
  await expect.poll(() => writes.length).toBe(4);
  expect(writes[2]).toMatchObject({
    display_name: "Synthetic Person",
    confirm_synthetic: true,
    skills: ["Python", "PostgreSQL"],
  });
  expect(writes[3]).toEqual({
    name: "Reliability candidates",
    search_id: searchId,
  });
  expect(JSON.stringify(writes[3])).not.toContain("opening_id");
});

test("FM12 publication requires review and confirmation and handles stale ETags safely", async ({
  page,
}) => {
  await mockReads(page);
  let publishCalls = 0;
  await page.route(
    `**${base}/openings/${openingId}/publication/publish`,
    async (route) => {
      publishCalls += 1;
      expect(route.request().headers()["if-match"]).toBe(
        publication.source_etag,
      );
      expect(route.request().postDataJSON()).toEqual({
        confirmed: true,
        preview_digest: publication.preview_digest,
      });
      await route.fulfill({
        status: publishCalls === 1 ? 409 : 200,
        json:
          publishCalls === 1
            ? { current: opening }
            : {
                ...publication,
                publication_state: "PUBLISHED",
                public_url: `/roles/${openingId}/`,
              },
      });
    },
  );
  await page.goto(fixture);
  const region = page.getByRole("region", {
    name: `Publication for ${opening.title}`,
  });
  const publish = region.getByRole("button", { name: "Publish", exact: true });
  await expect(publish).toBeDisabled();
  await region.getByRole("button", { name: "Preview" }).click();
  await expect(region.getByText(opening.description)).toBeVisible();
  await publish.click();
  await page.getByRole("button", { name: "Cancel" }).click();
  expect(publishCalls).toBe(0);
  await publish.click();
  await page.getByRole("button", { name: "Confirm publication" }).click();
  await expect(region.getByRole("status")).toContainText(
    "Nothing was published",
  );
  await region.getByRole("button", { name: "Preview" }).click();
  await publish.click();
  await page.getByRole("button", { name: "Confirm publication" }).click();
  await expect(region.getByText("Public: PUBLISHED")).toBeVisible();
});

test("FM12 organization reflows and passes serious accessibility checks", async ({
  page,
}) => {
  await mockReads(page);
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(fixture);
    await page.locator("html").evaluate((node, factor) => {
      node.style.zoom = String(factor);
    }, zoom);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(
      (
        await new AxeBuilder({ page: page as never }).analyze()
      ).violations.filter((item) =>
        ["serious", "critical"].includes(item.impact ?? ""),
      ),
    ).toEqual([]);
    await expect(page).toHaveScreenshot(`organization-${width}-${zoom}x.png`, {
      fullPage: true,
      animations: "disabled",
    });
  }
});
