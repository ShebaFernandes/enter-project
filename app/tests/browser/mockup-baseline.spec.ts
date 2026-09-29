import { expect, test } from "@playwright/test";

const widths = [320, 375, 768, 1024, 1440];

for (const width of widths) {
  test(`mockup login baseline at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/enter_recruiter_recruiter_candidate_ux.html");
    await expect(page).toHaveTitle(/Talent Platform Mockup/);
    await expect(page).toHaveScreenshot(`login-${width}.png`, {
      fullPage: true,
    });
  });
}

test("mockup reflows at 200 percent zoom", async ({ page }) => {
  await page.setViewportSize({ width: 640, height: 1000 });
  await page.goto("/enter_recruiter_recruiter_candidate_ux.html");
  await page.locator("html").evaluate((element) => {
    element.style.zoom = "2";
  });
  await expect(page).toHaveScreenshot("login-200-percent.png", {
    fullPage: true,
  });
});
