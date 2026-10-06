import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const origin = process.env.FM3_ORIGIN;
const output =
  process.env.FM3_LIVE_OUTPUT ?? "../docs/evidence/frontend-migration/fm3";
test.skip(!origin, "Run against the isolated FM3 Django verification server");

test("FM3 real chooser, candidate profile and keyboard return", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const [width, height, zoom] of [
    [1440, 1000, 1],
    [1024, 768, 1],
    [390, 844, 1],
    [320, 844, 1],
    [1440, 1000, 2],
  ]) {
    await page.setViewportSize({ width, height });
    await page.goto(origin!);
    await expect(page.locator("[data-react-page]")).toHaveAttribute(
      "data-owner",
      "react",
    );
    await page.locator("html").evaluate((el, factor) => {
      el.style.zoom = String(factor);
    }, zoom);
    expect(
      (await new AxeBuilder({ page: page as never }).analyze()).violations,
    ).toEqual([]);
    await expect(page).toHaveScreenshot(`chooser-live-${width}-${zoom}x.png`, {
      fullPage: true,
      animations: "disabled",
    });
    await page
      .getByRole("link", { name: /Candidate platform.*Upload/ })
      .click();
    await expect(page).toHaveURL(`${origin}/candidate/profile/`);
    await expect(
      page.getByRole("heading", { name: "Right person. Right problem." }),
    ).toBeVisible();
    await expect(page.locator("body")).toHaveAttribute(
      "data-frontend-renderer",
      "legacy",
    );
    expect(
      (await new AxeBuilder({ page: page as never }).analyze()).violations,
    ).toEqual([]);
    await page.screenshot({
      path: `${output}/candidate-profile-live-${width}-${zoom}x.png`,
      fullPage: true,
    });
    await page.goBack();
    await expect(
      page.getByRole("heading", { name: "Welcome to Enter" }),
    ).toBeVisible();
  }
});

test("FM3 real OIDC entry stops before the external provider", async ({
  page,
}) => {
  await page.route(/^https:\/\//, (route) => route.abort());
  await page.goto(origin!);
  const redirect = page.waitForResponse(
    (response) => response.url() === `${origin}/api/v1/auth/login`,
  );
  await page.getByRole("link", { name: /Recruiter.*Search/ }).click();
  const response = await redirect;
  expect(response.status()).toBe(302);
  const target = new URL(response.headers()["location"]);
  expect(target.searchParams.get("code_challenge_method")).toBe("S256");
  expect(target.searchParams.get("state")).toBeTruthy();
  expect(target.searchParams.get("nonce")).toBeTruthy();
  expect(target.searchParams.has("code_verifier")).toBe(false);
});
