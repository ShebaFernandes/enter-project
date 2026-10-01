import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const token = "a".repeat(43);
const fixture = `/app/tests/browser/fixtures/fm5.html#handoff=${token}`;
const groupId = "00000000-0000-4000-8000-000000000002";
const criterionId = "00000000-0000-4000-8000-000000000003";
const initial = () => ({
  etag: '"one"',
  schema_version: 1,
  version: 1,
  kind: "criteria-review",
  workflow_id: "00000000-0000-4000-8000-000000000004",
  criteria: {
    context: { type: "AD_HOC" },
    limit: 25,
    groups: [
      {
        id: groupId,
        label: "Core skills",
        purpose: "REQUIREMENT",
        operator: "ALL",
      },
    ],
    criteria: [
      {
        id: criterionId,
        group_id: groupId,
        field: "skill",
        operator: "CONTAINS",
        value: "Python",
      },
    ],
  },
  estimated_count: 12,
  group_impacts: [
    {
      group_id: groupId,
      operator: "ALL",
      estimated_count: 12,
      alternate_operator: "ANY",
      alternate_estimated_count: 18,
    },
  ],
});

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ json: { authenticated: true } }),
  );
  let state = initial();
  await page.route("**/search-handoffs/criteria-review", async (route) => {
    expect(route.request().headers()["x-workflow-handoff"]).toBe(token);
    if (route.request().method() === "PATCH") {
      expect(route.request().headers()["x-csrftoken"]).toBe("synthetic-csrf");
      state = {
        ...state,
        criteria: route.request().postDataJSON().criteria,
        etag: '"two"',
      };
    }
    await route.fulfill({ json: state });
  });
});

test("FM5 edits retain stable IDs and human values; confirmation alone executes", async ({
  page,
}) => {
  let executions = 0;
  await page.route("**/searches", async (route) => {
    executions++;
    const criteria = route.request().postDataJSON();
    expect(criteria.criteria[0].id).toBe(criterionId);
    expect(criteria.criteria[0].value).toBe("Edited Python");
    expect(criteria.groups[0].id).toBe(groupId);
    expect(criteria.groups[0].operator).toBe("ANY");
    await route.fulfill({
      json: { search_id: "00000000-0000-4000-8000-000000000005" },
    });
  });
  await page.route("**/search-handoffs/search-results", (route) =>
    route.fulfill({ status: 201, json: { token: "b".repeat(43) } }),
  );
  await page.route("**/recruiter/search/?view=results", (route) =>
    route.fulfill({ body: "Legacy results destination" }),
  );
  await page.goto(fixture);
  await page.getByLabel("Value", { exact: true }).fill("Edited Python");
  await page.getByLabel("Match within group").selectOption("ANY");
  await expect(page.getByText("Estimated impact updated.")).toBeVisible();
  expect(executions).toBe(0);
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  expect(executions).toBe(1);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM5 responsive review, keyboard, empty and add/remove groups", async ({
  page,
}) => {
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(fixture);
    await expect(page.getByLabel("Value", { exact: true })).toHaveValue(
      "Python",
    );
    await page.evaluate((factor) => {
      document.documentElement.style.zoom = String(factor);
    }, zoom);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page).toHaveScreenshot(`review-${width}-${zoom}.png`, {
      fullPage: true,
      animations: "disabled",
    });
    expect(
      (
        await new AxeBuilder({ page: page as never }).analyze()
      ).violations.filter((v) =>
        ["serious", "critical"].includes(v.impact ?? ""),
      ),
    ).toEqual([]);
  }
  await page.getByRole("button", { name: "Remove group" }).click();
  await expect(page.getByText("No criteria groups yet")).toBeVisible();
  await page.getByRole("button", { name: "Add group", exact: true }).click();
  await page
    .getByRole("button", { name: "Add criterion", exact: true })
    .click();
  await expect(page.getByLabel("Value", { exact: true })).toBeFocused();
});

test("FM5 expired restore exposes no criteria and offers a safe return", async ({
  page,
}) => {
  await page.route("**/search-handoffs/criteria-review", (route) =>
    route.fulfill({ status: 404, json: {} }),
  );
  await page.goto(fixture);
  await expect(page.getByRole("alert")).toContainText("expired");
  await expect(page.getByLabel("Value", { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Return to search" }),
  ).toHaveAttribute("href", /\/recruiter\/search\/$/);
});

test("FM5 conflict retains human edits and requires explicit reconciliation", async ({
  page,
}) => {
  let state = initial();
  let stale = true;
  let writes = 0;
  await page.route("**/search-handoffs/criteria-review", async (route) => {
    if (route.request().method() === "PATCH") {
      writes++;
      if (stale) {
        stale = false;
        state = { ...state, etag: '"newer"' };
        await route.fulfill({ status: 409, json: {} });
        return;
      }
      expect(route.request().headers()["if-match"]).toBe('"newer"');
      state = { ...state, criteria: route.request().postDataJSON().criteria };
    }
    await route.fulfill({ json: state });
  });
  await page.goto(fixture);
  await page.getByLabel("Value", { exact: true }).fill("Human correction");
  await expect(
    page.getByRole("region", { name: "Resolve changed information" }),
  ).toBeFocused();
  await expect(page.getByLabel("Value", { exact: true })).toHaveValue(
    "Human correction",
  );
  expect(writes).toBe(1);
  await page.getByRole("button", { name: "Resubmit reviewed changes" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Estimated impact updated",
  );
  expect(writes).toBe(2);
  await expect(page.getByLabel("Value", { exact: true })).toHaveValue(
    "Human correction",
  );
});

test("FM5 validation throttling and degraded saves preserve editable drafts", async ({
  page,
}) => {
  for (const [status, message] of [
    [422, "validate"],
    [429, "Too many requests"],
    [503, "unavailable"],
  ] as const) {
    await page.goto("about:blank");
    await page.route("**/search-handoffs/criteria-review", (route) =>
      route.fulfill(
        route.request().method() === "GET"
          ? { json: initial() }
          : { status, json: {} },
      ),
    );
    await page.goto(fixture);
    await page.getByLabel("Value", { exact: true }).fill("Edited safely");
    await expect(page.getByRole("alert")).toContainText(message);
    await expect(page.getByLabel("Value", { exact: true })).toHaveValue(
      "Edited safely",
    );
    await expect(page.getByLabel("Value", { exact: true })).toBeEnabled();
  }
});

test("FM5 handoff retry never executes the confirmed search twice", async ({
  page,
}) => {
  let searches = 0;
  let attempts = 0;
  let retryKey = "";
  await page.route("**/searches", (route) => {
    searches++;
    return route.fulfill({
      json: { search_id: "00000000-0000-4000-8000-000000000005" },
    });
  });
  await page.route("**/search-handoffs/search-results", (route) => {
    const key = route.request().headers()["idempotency-key"];
    if (!retryKey) retryKey = key;
    expect(key).toBe(retryKey);
    attempts++;
    return route.fulfill(
      attempts === 1
        ? { status: 503, json: {} }
        : { json: { token: "b".repeat(43) } },
    );
  });
  await page.route("**/recruiter/search/?view=results", (route) =>
    route.fulfill({ body: "Legacy results" }),
  );
  await page.goto(fixture);
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await page.getByRole("button", { name: "Retry opening results" }).click();
  await expect(page).toHaveURL(/view=results#handoff=/);
  expect(searches).toBe(1);
  expect(attempts).toBe(2);
});

test("FM5 keyboard skip focus, typed values and membership retain stable references", async ({
  page,
}) => {
  await page.goto(fixture);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to main content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await expect(page).toHaveURL(/#handoff=/);
  await page.getByRole("button", { name: "Add group", exact: true }).click();
  await page
    .getByLabel("Purpose", { exact: true })
    .last()
    .selectOption("EXCLUSION");
  await page
    .getByLabel("Group membership")
    .selectOption({ label: "Recruiter-defined group" });
  await expect(page.getByLabel("Value", { exact: true })).toBeFocused();
  await expect(page.getByText(criterionId, { exact: true })).toHaveCount(1);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("FM5 list and false values are transported without string coercion", async ({
  page,
}) => {
  const values: unknown[] = [];
  await page.route("**/search-handoffs/criteria-review", async (route) => {
    const state = initial();
    if (route.request().method() === "PATCH") {
      state.criteria = route.request().postDataJSON().criteria;
      values.push(state.criteria.criteria[0].value);
    }
    await route.fulfill({ json: state });
  });
  await page.goto(fixture);
  await page.getByLabel("Operator", { exact: true }).selectOption("IN");
  await page.getByLabel("Value", { exact: true }).fill('["Python","Django"]');
  await expect(page.getByRole("status")).toContainText(
    "Estimated impact updated",
  );
  expect(values.at(-1)).toEqual(["Python", "Django"]);
  await page.getByLabel("Operator", { exact: true }).selectOption("EXISTS");
  await page.getByLabel("Value", { exact: true }).fill("false");
  await expect.poll(() => values.at(-1)).toBe(false);
});

test("FM5 loading restoration retry and uncertain execution fail safely", async ({
  page,
}) => {
  let first = true;
  await page.route("**/search-handoffs/criteria-review", async (route) => {
    if (first) {
      first = false;
      await route.fulfill({ status: 503, json: {} });
    } else await route.fulfill({ json: initial() });
  });
  await page.route("**/searches", (route) => route.abort("failed"));
  await page.goto(fixture);
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await page.getByRole("button", { name: "Retry restoration" }).click();
  await expect(page.getByLabel("Value", { exact: true })).toHaveValue("Python");
  await page.getByRole("button", { name: "Run confirmed search" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "will not be submitted again automatically",
  );
  await expect(
    page.getByRole("button", { name: "Run confirmed search" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("link", { name: "Return to search" }),
  ).toBeVisible();
});
