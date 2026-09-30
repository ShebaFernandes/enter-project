import { expect, test } from "@playwright/test";

test("signed-in recruiter navigation signs out completely and protects history", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:4173");
  await page.setContent(
    `<div data-recruiter-search data-tenant-id="synthetic"><header><p>Signed in as recruiter</p><button data-sign-out>Sign out</button></header><form data-search-form><textarea name="prompt"></textarea><select name="context"><option>AD_HOC</option></select><input name="opening_id"><div data-criteria-list></div></form><button data-add-criterion></button><button data-speech></button><p data-speech-status></p><div class="search-status"></div><button data-more hidden></button><div data-results tabindex="-1"></div><dialog data-candidate-dialog><div data-detail></div><button data-close-detail></button></dialog></div>`,
  );
  await page.evaluate(() => sessionStorage.setItem("sensitive", "draft"));
  let signedOut = false;
  await page.route("**/api/v1/session/sign-out", (route) => {
    signedOut = true;
    return route.fulfill({ status: 204, body: "" });
  });
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({ status: 200, body: "Signed out" }),
  );
  await page.addScriptTag({
    path: "static/dist/assets/app.js",
    type: "module",
  });
  const button = page.getByRole("button", { name: "Sign out" });
  await button.focus();
  await expect(button).toBeFocused();
  await button.click();
  await expect.poll(() => signedOut).toBe(true);
  await expect(page).toHaveURL(/auth\/login/);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
});

test("recruiter entry does not expose identity eligibility details", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({
      status: 403,
      json: { title: "Identity response unavailable" },
    }),
  );
  const response = await page.goto("http://127.0.0.1:4173/api/v1/auth/login");
  expect(response).not.toBeNull();
  expect(response!.status()).toBe(403);
  expect(await response!.text()).not.toContain("gmail");
  expect(await response!.text()).not.toContain("membership");
});
