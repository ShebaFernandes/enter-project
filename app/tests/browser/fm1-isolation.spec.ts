import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("legacy draft restoration waits for the criterion renderer", async ({
  page,
}) => {
  const template = await readFile(
    "frontend/templates/recruiter/search.html",
    "utf8",
  );
  await page.route("**/fm1-legacy", (route) =>
    route.fulfill({
      contentType: "text/html",
      body:
        template +
        '<script type="module" src="/app/static/dist/assets/app.js"></script>',
    }),
  );
  await page.addInitScript(() => {
    sessionStorage.setItem(
      "recruiter-search-draft-v1",
      JSON.stringify({
        prompt: "Synthetic Python search",
        context: "AD_HOC",
        openingId: "",
        criteria: [1, 2].map(() => ({
          purpose: "REQUIREMENT",
          group_operator: "ANY",
          field: "skill",
          operator: "CONTAINS",
          value: "Python",
        })),
        filter: "all",
        selection: "",
      }),
    );
  });
  await page.goto("/fm1-legacy", { timeout: 5000 });
  await expect(page.getByLabel("Value")).toHaveCount(2);
  await expect(page.getByLabel("Describe the candidate you need")).toHaveValue(
    "Synthetic Python search",
  );
});

test("legacy bundle has no Tailwind reset or React mount and retains native styling", async ({
  page,
}) => {
  const css = await readFile("static/dist/assets/app.css", "utf8");
  const js = await readFile("static/dist/assets/app.js", "utf8");
  expect(css).not.toContain("tailwindcss");
  expect(css).not.toContain("@layer");
  expect(js).not.toContain("data-react-candidate-profile");
  expect(js).not.toContain("data-react-recruiter-search");
  await page.goto("/");
  await page.setContent(
    "<h1>Legacy heading</h1><button>Legacy control</button><fieldset><legend>Group</legend></fieldset>",
  );
  await page.addStyleTag({ content: css });
  const styles = await page.locator("button").evaluate((el) => {
    const s = getComputedStyle(el);
    return { background: s.backgroundColor, minHeight: s.minHeight };
  });
  expect(styles.background).toBe("rgb(22, 78, 99)");
  expect(styles.minHeight).toBe("44px");
});

test("isolated checkpoint preview mounts React without legacy initialization", async ({
  page,
}) => {
  await page.goto("/");
  await page.setContent("<div data-react-recruiter-search></div>");
  await page.addStyleTag({ path: "static/dist/wip/assets/app.css" });
  await page.addScriptTag({
    path: "static/dist/wip/assets/app.js",
    type: "module",
  });
  await expect(
    page.getByRole("heading", { name: "Find your next great hire." }),
  ).toBeVisible();
  // Legacy search initializes criterion fields. Their absence proves no competing renderer.
  await expect(page.locator("[data-criteria-list] input")).toHaveCount(0);
  const css = await readFile("static/dist/wip/assets/app.css", "utf8");
  expect(css).not.toContain("box-sizing:border-box");
});
