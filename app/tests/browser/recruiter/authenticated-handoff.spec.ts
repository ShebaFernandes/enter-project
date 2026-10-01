import { expect, test } from "@playwright/test";
import { localBootstrap } from "../local-bootstrap";
import AxeBuilder from "@axe-core/playwright";

test("authenticated legacy review results comparison refresh and return keep protected state out of storage", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM4_BOOTSTRAP_URL");
  test.skip(
    !bootstrap,
    "Requires one-time existing synthetic recruiter bootstrap",
  );
  await page.goto(bootstrap!);
  if (process.env.FM4_AUTH_ORIGIN) {
    await expect(page.locator("body")).toHaveAttribute(
      "data-frontend-renderer",
      "react",
    );
    for (const [width, height, zoom] of [
      [1440, 1000, 1],
      [1024, 768, 1],
      [390, 844, 1],
      [320, 844, 1],
      [1440, 1000, 2],
    ]) {
      await page.setViewportSize({ width, height });
      await page.evaluate((value) => {
        document.documentElement.style.zoom = String(value);
      }, zoom);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `../docs/evidence/frontend-migration/fm4/search-home-live-${width}-${zoom}x.png`,
        fullPage: true,
      });
      await page.getByRole("button", { name: "Projects and recents" }).click();
      await page.screenshot({
        path: `../docs/evidence/frontend-migration/fm4/sidebar-live-${width}-${zoom}x.png`,
        fullPage: true,
      });
      await page.keyboard.press("Escape");
    }
    await page.evaluate(() => {
      document.documentElement.style.zoom = "1";
    });
    await page.setViewportSize({ width: 1280, height: 720 });
  }
  await page.getByLabel("Describe the candidate you need").fill("Python");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page).toHaveURL(/criteria-review\/#handoff=/);
  await expect(page.getByRole("status")).toContainText("Criteria restored");
  await page.reload();
  await expect(page.getByRole("status")).toContainText("Criteria restored");
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page).toHaveURL(/search\/\?view=results#handoff=/);
  await page.getByLabel("Compare Synthetic Search Candidate").check();
  await page.getByLabel("Compare Synthetic Comparison Candidate").check();
  await expect(
    page.getByText("2 candidates selected for comparison."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Compare selected candidates" })
    .click();
  await expect(page).toHaveURL(/comparison\/#handoff=/);
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  expect(
    await page.evaluate(() => ({
      local: { ...localStorage },
      session: { ...sessionStorage },
    })),
  ).toEqual({ local: {}, session: {} });
  const audit = await new AxeBuilder({ page: page as never }).analyze();
  expect(
    audit.violations.filter((item) =>
      ["serious", "critical"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
  await page.getByRole("button", { name: "Return to results" }).click();
  await expect(page).toHaveURL(/search\/\?view=results#handoff=/);
  await expect(
    page.getByLabel("Compare Synthetic Search Candidate"),
  ).toBeChecked();
  if (process.env.FM4_AUTH_ORIGIN) {
    const home = page.url().split("?")[0];
    await page.goto(home);
    await page.getByRole("button", { name: "Projects and recents" }).click();
    await page
      .getByRole("button", { name: "Recent search 1", exact: true })
      .click();
    await expect(page).toHaveURL(/criteria-review\/#handoff=/);
    await expect(page.getByRole("status")).toContainText("Criteria restored");
    await page.goto(home);
  }
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).not.toHaveURL(/recruiter\/search/);
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Who are we hiring today?" }),
  ).toHaveCount(0);
});

test("authenticated persisted pagination supports refresh Back and safe comparison return", async ({
  page,
}) => {
  const bootstrap = localBootstrap("LOCAL_FM4_BOOTSTRAP_URL");
  test.skip(!bootstrap, "Requires synthetic authenticated verification server");
  await page.goto(bootstrap!);
  const destination = await page.evaluate(async () => {
    const tenant = location.pathname.split("/")[2];
    const csrf = document.querySelector<HTMLInputElement>(
      "[name=csrfmiddlewaretoken]",
    )!.value;
    const base = `/api/v1/tenants/${tenant}`;
    const headers = {
      "Content-Type": "application/json",
      "X-CSRFToken": csrf,
      "X-Tenant-ID": tenant,
    };
    const group = crypto.randomUUID();
    const run = await fetch(`${base}/searches`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        context: { type: "AD_HOC" },
        groups: [
          { id: group, purpose: "REQUIREMENT", operator: "ANY", label: "Core" },
        ],
        criteria: [
          {
            id: crypto.randomUUID(),
            group_id: group,
            field: "skill",
            operator: "CONTAINS",
            value: "Python",
          },
        ],
        limit: 1,
      }),
    });
    if (!run.ok) throw new Error("Synthetic search failed");
    const result = await run.json();
    const handoff = await fetch(`${base}/search-handoffs/search-results`, {
      method: "POST",
      headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ search_id: result.search_id }),
    });
    if (!handoff.ok) throw new Error("Synthetic handoff failed");
    return `/tenants/${tenant}/recruiter/search/?view=results#handoff=${(await handoff.json()).token}`;
  });
  await page.goto(new URL(destination, page.url()).href);
  await expect(page.getByRole("article")).toHaveCount(1);
  const first = page.url();
  await page.getByRole("button", { name: "Load more" }).click();
  await expect(page.getByRole("article")).toHaveCount(2);
  const second = page.url();
  expect(second).not.toBe(first);
  await page.reload();
  await expect(page.getByRole("article")).toHaveCount(2);
  await page.goBack();
  await expect(page.getByRole("article")).toHaveCount(1);
  await page.goForward();
  await expect(page.getByRole("article")).toHaveCount(2);
  await page.getByLabel("Compare Synthetic Search Candidate").check();
  await page.getByLabel("Compare Synthetic Comparison Candidate").check();
  await page
    .getByRole("button", { name: "Compare selected candidates" })
    .click();
  await expect(
    page.getByText("2 currently authorized candidates loaded."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Return to results" }).click();
  await expect(page.getByRole("article")).toHaveCount(2);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});
