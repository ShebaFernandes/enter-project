import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import AxeBuilder from "@axe-core/playwright";

const origin = process.env.FM1_ORIGIN ?? "http://127.0.0.1:8001";
const output = "../docs/evidence/frontend-migration/fm1-baselines";
const mockup =
  process.env.FM1_MOCKUP ??
  "/Users/enter/Documents/Codex/2026-09-25/fix/outputs/enter_recruiter_recruiter_candidate_ux.html";
const expectedHash =
  "daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9";

function bootstrap(role: string): { url: string; tenant_id?: string } {
  return JSON.parse(
    execFileSync(
      ".venv/bin/python",
      ["manage.py", `bootstrap_local_${role}`, "--base-url", origin, "--json"],
      { encoding: "utf8" },
    ),
  );
}

test("FM1 authenticated page and immutable mockup baseline capture", async ({
  browser,
}) => {
  test.skip(
    process.env.FM1_CAPTURE !== "1",
    "Explicit synthetic baseline capture only",
  );
  test.setTimeout(240_000);
  await mkdir(output, { recursive: true });
  const records: object[] = [];
  if (process.env.FM1_REFERENCE_ONLY === "1") {
    const prior = JSON.parse(
      await readFile(`${output}/manifest.json`, "utf8"),
    ) as { records: { reference: boolean }[] };
    records.push(...prior.records.filter((record) => !record.reference));
  }
  const screenshot = async (page: Page, name: string, reference = false) => {
    await page.evaluate(() => document.fonts.ready);
    const accessibility = reference
      ? null
      : await new AxeBuilder({ page: page as never }).analyze();
    const violations =
      accessibility?.violations.map(({ id, impact }) => ({ id, impact })) ?? [];
    for (const [width, height, zoom] of [
      [1440, 1000, 1],
      [1024, 768, 1],
      [390, 844, 1],
      [320, 844, 1],
      [1440, 1000, 2],
    ]) {
      await page.setViewportSize({ width, height });
      await page.locator("html").evaluate((el, value) => {
        el.style.zoom = String(value);
      }, zoom);
      await page.screenshot({
        path: `${output}/${name}-${width}x${height}-${zoom}x.png`,
        fullPage: true,
        animations: "disabled",
      });
    }
    await page.locator("html").evaluate((el) => {
      el.style.zoom = "1";
    });
    records.push({ name, reference, violations });
  };

  if (process.env.FM1_REFERENCE_ONLY !== "1") {
    const recruiter = await browser.newContext();
    const page = await recruiter.newPage();
    page.on("dialog", (dialog) => dialog.accept());
    await page.goto(bootstrap("recruiter").url);
    await expect(page.locator("body")).toHaveAttribute(
      "data-frontend-renderer",
      "legacy",
    );
    await expect(page.getByLabel("Value")).toBeVisible();
    const searchUrl = page.url();
    const tenant = new URL(searchUrl).pathname.split("/")[2];
    await screenshot(page, "production-search-home");
    await page
      .getByLabel("Describe the candidate you need")
      .fill("Python engineers");
    await page.getByLabel("Value").fill("Python");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Synthetic Search Candidate" }),
    ).toBeVisible();
    await screenshot(page, "production-results");
    await page
      .getByRole("button", { name: "View authorized details" })
      .first()
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await screenshot(page, "production-detail-dialog");
    const managementUrl = await page
      .getByRole("link", { name: "Manage this candidate" })
      .getAttribute("href");
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await page.getByLabel("Compare Synthetic Search Candidate").check();
    await page.getByLabel("Compare Synthetic Comparison Candidate").check();
    await page
      .getByRole("button", { name: "Compare selected candidates" })
      .click();
    await expect(
      page.getByText("2 currently authorized candidates loaded."),
    ).toBeVisible();
    await screenshot(page, "production-comparison");
    await page.goto(origin + managementUrl);
    await expect(
      page.getByRole("heading", { name: "403 Forbidden" }),
    ).toBeVisible();
    await screenshot(page, "production-management-direct-navigation-denied");
    // Existing page requires the tenant header; record the direct-navigation defect above.
    await recruiter.setExtraHTTPHeaders({ "X-Tenant-ID": tenant });
    await page.goto(origin + managementUrl);
    await expect(page.locator("[data-candidate-management]")).toBeVisible();
    await expect(page.locator("[data-detail]")).toHaveCount(0);
    await page.waitForLoadState("networkidle");
    await screenshot(page, "production-management-disclosure");
    await page.goto(`${origin}/tenants/${tenant}/recruiter/organization/`);
    await page.waitForLoadState("networkidle");
    await screenshot(page, "production-organization");
    const reviewPage = await recruiter.newPage();
    reviewPage.on("dialog", (dialog) => dialog.accept());
    await reviewPage.goto(searchUrl);
    await reviewPage
      .getByLabel("Describe the candidate you need")
      .fill("Maybe an engineer");
    await reviewPage
      .getByRole("button", { name: "Search", exact: true })
      .click();
    await expect(reviewPage).toHaveURL(/criteria-review/);
    await expect(
      reviewPage.getByText(/estimated candidates in scope/),
    ).toBeVisible();
    await screenshot(reviewPage, "production-criteria-review");

    const candidate = await browser.newContext();
    const candidatePage = await candidate.newPage();
    candidatePage.on("dialog", (dialog) => dialog.accept());
    await candidatePage.goto(bootstrap("candidate").url);
    await expect(candidatePage.getByRole("heading", { level: 1 })).toHaveText(
      "Software Engineer",
    );
    await screenshot(candidatePage, "production-role-application");
    for (const [path, name] of [
      ["/candidate/profile/", "profile-resume"],
      ["/candidate/applications/", "progress"],
      ["/candidate/rights/", "rights"],
    ]) {
      await candidatePage.goto(origin + path);
      await candidatePage.waitForLoadState("networkidle");
      await screenshot(candidatePage, `production-${name}`);
    }
    const admin = await browser.newContext();
    const adminPage = await admin.newPage();
    await adminPage.goto(bootstrap("tenant_admin").url);
    await expect(
      adminPage.getByRole("heading", { name: "Tenant governance" }),
    ).toBeVisible();
    await screenshot(adminPage, "production-governance");
    await adminPage.getByRole("tab", { name: "Audit metadata" }).click();
    await adminPage.waitForLoadState("networkidle");
    await screenshot(adminPage, "production-audit");
    await Promise.all([recruiter.close(), candidate.close(), admin.close()]);
  }

  const source = await readFile(mockup);
  expect(createHash("sha256").update(source).digest("hex")).toBe(expectedHash);
  const reference = await browser.newContext();
  // Reference only: remove nondeterministic remote font dependence without editing the source.
  await reference.route(/fonts\.(googleapis|gstatic)\.com/, (route) =>
    route.abort(),
  );
  const ref = await reference.newPage();
  ref.on("dialog", (dialog) => dialog.accept());
  await ref.route("**/fm1-reference.html", (route) =>
    route.fulfill({ contentType: "text/html", body: source }),
  );
  await ref.goto("http://127.0.0.1:4173/fm1-reference.html");
  await screenshot(ref, "mockup-chooser", true);
  await ref.locator("#candidatePortalBtn").click();
  await screenshot(ref, "mockup-candidate-platform", true);
  await ref.goto("http://127.0.0.1:4173/fm1-reference.html");
  await ref.locator("#recruiterEmail").fill("reviewer@synthetic.example");
  await ref.locator(".primary-choice").click();
  await expect(ref.locator("#home")).toBeVisible();
  await screenshot(ref, "mockup-search-home", true);
  await ref.locator("#searchSidePanelToggle").click();
  await screenshot(ref, "mockup-sidebar", true);
  await ref.locator("#searchSidePanelToggle").click();
  await ref.locator("#searchInput").fill("Java");
  await ref.locator("#searchBtn").click();
  await expect(ref.locator("#results")).toBeVisible();
  await screenshot(ref, "mockup-results", true);
  await ref.locator("[data-profile-id]").first().click();
  await screenshot(ref, "mockup-detail", true);
  await ref.locator('[data-profile-tab="notes"]').click();
  await screenshot(ref, "mockup-notes", true);
  await ref.locator('[data-profile-tab="action"]').click();
  await screenshot(ref, "mockup-action", true);
  await ref.locator("[data-close-profile]").click();
  const compare = ref.locator("[data-compare-id]");
  if ((await compare.count()) >= 2) {
    await compare.nth(0).check();
    await ref.locator("[data-compare-id]").nth(1).check();
    await ref.locator("#compareSelectedBtn").click();
    await screenshot(ref, "mockup-comparison", true);
    await ref.locator("[data-close-compare]").click();
  }
  // Dormant sections are reference-only captures; the mockup routes some IDs elsewhere.
  await ref.evaluate(() => {
    const demo = window as unknown as {
      renderInterpretation: () => void;
      renderAdmin: () => void;
    };
    demo.renderInterpretation();
    demo.renderAdmin();
  });
  for (const id of ["publicProfile", "interp", "admin"]) {
    await ref.evaluate((screen) => {
      document
        .querySelectorAll(".screen")
        .forEach((el) => el.classList.remove("active"));
      document.getElementById(screen)?.classList.add("active");
      document.body.classList.remove("home-shell-active");
    }, id);
    await screenshot(ref, `mockup-dormant-${id}`, true);
  }
  expect(
    createHash("sha256")
      .update(await readFile(mockup))
      .digest("hex"),
  ).toBe(expectedHash);
  await writeFile(
    `${output}/manifest.json`,
    JSON.stringify(
      { mockupHash: expectedHash, syntheticOnly: true, records },
      null,
      2,
    ),
  );
  await reference.close();
});
