import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

const fixture = "/app/tests/browser/fixtures/fm2.html";

test("foundation validation and reconciliation visual states", async ({
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
    await page.locator("html").evaluate((el, z) => {
      el.style.zoom = String(z);
    }, zoom);
    await page.getByRole("button", { name: "Validate example" }).click();
    await page.getByRole("button", { name: "Show conflict" }).click();
    const audit = await new AxeBuilder({ page: page as never }).analyze();
    expect(
      audit.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      ),
    ).toEqual([]);
    await expect(page).toHaveScreenshot(
      `reconciliation-${width}-${zoom}x.png`,
      { fullPage: true, animations: "disabled" },
    );
  }
});

test("foundation denies unavailable session and malformed bootstrap without rendering", async ({
  page,
}) => {
  const html = await readFile("tests/browser/fixtures/fm2.html", "utf8");
  await page.route("**/fm2.html", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: html.replace('"requiresSession": false', '"requiresSession": true'),
    }),
  );
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ status: 403, body: "Forbidden" }),
  );
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Page unavailable" }),
  ).toBeVisible();
  await expect(page.locator("[data-react-page]")).toBeEmpty();
  expect(
    await page.evaluate(async () => {
      const path = "/app/static/dist/react/assets/app.js";
      const { readBootstrap } = await import(path);
      let denied = 0;
      for (const value of [
        "null",
        "{}",
        '{"version":1,"page":"x","requiresSession":true,"tenantId":"../../other"}',
      ]) {
        const element = document.createElement("script");
        element.type = "application/json";
        element.textContent = value;
        try {
          readBootstrap(element);
        } catch {
          denied++;
        }
      }
      return denied;
    }),
  ).toBe(3);
});

test("foundation conflict actions are explicit and pagehide clears component memory", async ({
  page,
}) => {
  await page.goto(fixture);
  await page.getByRole("button", { name: "Show conflict" }).click();
  await expect(
    page.getByRole("region", { name: "Resolve changed information" }),
  ).toBeFocused();
  await expect(
    page.getByText("Stored: Stored example; attempted: Edited example"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Review and merge" }).click();
  await expect(page.getByRole("status").first()).toHaveText(
    "Review requested. Changes are not submitted.",
  );
  await page
    .getByLabel("Example label", { exact: true })
    .fill("Ephemeral synthetic edit");
  await page.evaluate(() =>
    window.dispatchEvent(new PageTransitionEvent("pagehide")),
  );
  await expect(page.locator("[data-react-page]")).toBeEmpty();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("foundation keyboard, labels, validation, dialog and ephemeral state", async ({
  page,
}) => {
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Shared design foundation" }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to main content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByRole("button", { name: "Validate example" }).click();
  await expect(
    page.getByLabel("Example label", { exact: true }),
  ).toHaveAttribute("aria-invalid", "true");
  await expect(
    page.getByRole("alert").filter({ hasText: "Enter a value" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open dialog" }).click();
  await expect(
    page.getByRole("dialog", { name: "Review changes" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Close dialog" }),
  ).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(
    page.getByRole("button", { name: "Keep editing" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Open dialog" })).toBeFocused();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("foundation isolated styles, responsive visual states and accessibility", async ({
  page,
}) => {
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Shared design foundation" }),
  ).toBeVisible();
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.locator("html").evaluate((el, z) => {
      el.style.zoom = String(z);
    }, zoom);
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      ),
    ).toBe(true);
    const results = await new AxeBuilder({ page: page as never }).analyze();
    expect(
      results.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      ),
    ).toEqual([]);
    await expect(page).toHaveScreenshot(`foundation-${width}-${zoom}x.png`, {
      fullPage: true,
      animations: "disabled",
    });
    await page.getByRole("button", { name: "Open dialog" }).click();
    const dialogAudit = await new AxeBuilder({ page: page as never }).analyze();
    expect(
      dialogAudit.violations.filter(
        (v) => v.impact === "serious" || v.impact === "critical",
      ),
    ).toEqual([]);
    await expect(page).toHaveScreenshot(`dialog-${width}-${zoom}x.png`, {
      animations: "disabled",
    });
    await page.keyboard.press("Escape");
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".ui-skeleton").first()).toHaveCSS(
    "animation-name",
    "none",
  );
  const css = await readFile("static/dist/react/assets/app.css", "utf8");
  await page.setContent("<h1>Legacy</h1><button>Legacy control</button>");
  const before = await page
    .locator("button")
    .evaluate((el) => [
      getComputedStyle(el).backgroundColor,
      getComputedStyle(el).padding,
    ]);
  expect(css).toContain(".enter-ui");
  await page.addStyleTag({ url: "/app/static/dist/react/assets/app.css" });
  expect(
    await page
      .locator("button")
      .evaluate((el) => [
        getComputedStyle(el).backgroundColor,
        getComputedStyle(el).padding,
      ]),
  ).toEqual(before);
});

test("foundation API transport preserves CSRF, versions and request keys without storage", async ({
  page,
}) => {
  await page.goto(fixture);
  const requests: Record<string, string>[] = [];
  await page.route("**/api/v1/**", async (route) => {
    requests.push(route.request().headers());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"ok":true}',
      headers: { ETag: '"2"' },
    });
  });
  const result = await page.evaluate(async () => {
    const path = "/app/static/dist/react/assets/app.js";
    const { sameOriginClient, responseJson } = await import(path);
    const client = sameOriginClient({
      tenantId: "00000000-0000-0000-0000-000000000001",
      csrfToken: () => "synthetic-test-csrf",
    });
    const response = await client(
      "/api/v1/tenants/00000000-0000-0000-0000-000000000001/example",
      {
        method: "PATCH",
        headers: {
          "If-Match": '"1"',
          "Idempotency-Key": "stable-test-key",
          "X-Tenant-ID": "wrong",
        },
        body: "{}",
      },
    );
    const data = await responseJson(response);
    let denied = 0;
    for (const url of [
      "https://example.test/api/v1/session",
      "/api/v1/tenants/other/example",
      "/outside",
    ]) {
      try {
        await client(url);
      } catch {
        denied++;
      }
    }
    return { data, denied };
  });
  expect(result.denied).toBe(3);
  expect(result.data.etag).toBe('"2"');
  expect(requests).toHaveLength(1);
  expect(requests[0]["x-csrftoken"]).toBe("synthetic-test-csrf");
  expect(requests[0]["x-tenant-id"]).toBe(
    "00000000-0000-0000-0000-000000000001",
  );
  expect(requests[0]["if-match"]).toBe('"1"');
  expect(requests[0]["idempotency-key"]).toBe("stable-test-key");
});

test("foundation refuses duplicate ownership and keeps safe fallback on bundle failure", async ({
  page,
}) => {
  await page.route("**/showcase/assets/app.js", (route) => route.abort());
  await page.goto(fixture);
  await expect(
    page.getByRole("heading", { name: "Page unavailable" }),
  ).toBeVisible();
  expect(await page.locator("[data-react-page]").innerHTML()).toBe("");
  await page.unroute("**/showcase/assets/app.js");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Shared design foundation" }),
  ).toBeVisible();
  expect(
    await page.evaluate(async () => {
      const path = "/app/static/dist/react/assets/app.js";
      const { mountPage } = await import(path);
      try {
        await mountPage({});
        return false;
      } catch {
        return true;
      }
    }),
  ).toBe(true);
});
