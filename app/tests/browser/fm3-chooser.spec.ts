import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFile } from "node:fs/promises";

const fixture = "/app/tests/browser/fixtures/fm3.html";

test("FM3 safe error, loading announcement and bundle recovery", async ({
  page,
}) => {
  const html = await readFile("tests/browser/fixtures/fm3.html", "utf8");
  await page.route("**/fm3.html", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: html.replace(
        '"requiresSession": false',
        '"requiresSession": false, "entryError": true',
      ),
    }),
  );
  await page.goto(fixture);
  await expect(page.getByRole("alert")).toContainText(
    "Sign-in could not be completed",
  );
  await page
    .locator("nav")
    .evaluate((el) =>
      el.addEventListener("click", (event) => event.preventDefault()),
    );
  await page.getByRole("link", { name: /Recruiter.*Search/ }).click();
  await expect(page.getByRole("status")).toHaveText(
    "Opening secure recruiter sign-in…",
  );
  await expect(page).toHaveScreenshot("chooser-error-loading.png", {
    fullPage: true,
    animations: "disabled",
  });
  await page.route("**/static/dist/react/assets/app.js", (route) =>
    route.abort(),
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Page unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Candidate platform" }),
  ).toHaveAttribute("href", "/jobs/");
});

test("FM3 chooser visual, responsive and accessibility states", async ({
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
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Choose your kingdom platform",
    );
    await page.locator("html").evaluate((el, factor) => {
      el.style.zoom = String(factor);
    }, zoom);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    expect(
      (await new AxeBuilder({ page: page as never }).analyze()).violations,
    ).toEqual([]);
    await expect(page).toHaveScreenshot(`chooser-${width}-${zoom}x.png`, {
      fullPage: true,
      animations: "disabled",
    });
  }
});

test("FM3 keyboard choices use fixed server endpoints without storage", async ({
  page,
}) => {
  await page.goto(fixture);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Choose your kingdom platform",
  );
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to main content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  const recruiter = page.getByRole("link", { name: /Recruiter.*Search/ });
  const candidate = page.getByRole("link", {
    name: /Candidate platform.*Explore/,
  });
  await expect(recruiter).toHaveAttribute("href", "/api/v1/auth/login");
  await expect(candidate).toHaveAttribute("href", "/jobs/");
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  await candidate.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/jobs\/$/);
});
