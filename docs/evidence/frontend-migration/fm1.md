# FM1 reconciliation and baseline evidence

Scope: FM1-01–FM1-03 only, 2026-10-01. No FM2, feature-page migration, API/model/migration change or Phase 10 work. Original mockup SHA-256: `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`. The external reference and root repository copy have identical hashes.

## Checkpoint inventory and decisions

The working tree was clean before FM1. Checkpoint `66a3acd9fbf8f1be9e45c568f18b1dd64e8fc5a6` contains all eleven WIP files; parent `5372072` contains the legacy fallback. No prior tests were removed. Retained checkpoint history preserves superseded WIP markup and CSS for review.

| Checkpoint file | Classification | FM1 decision / evidence |
|---|---|---|
| app/frontend/pages.tsx | unsafe and disabled | Incomplete React forms relied on legacy DOM mutation; nested main landmarks, different labels and inert controls preclude cutover. Retained with formatting only; isolated build preview, no production import or verified registration. |
| app/frontend/shared/bootstrap.ts | reusable after correction | Restore legacy entry imports; remove React/Tailwind imports from production. |
| app/frontend/styles/forms.css | superseded | Undo global base-layer wrapper to restore the legacy cascade exactly. WIP change retained in checkpoint. |
| app/frontend/styles/recruiter-search.css | superseded | Restore removed criteria-panel border/padding from parent; no approved legacy redesign. |
| app/frontend/styles/tailwind.css | reusable after correction | Preserve theme/utilities-only imports, format, isolate in WIP-only build. No reset/preflight in either production or preview CSS. Theme completeness belongs to FM2. |
| app/frontend/templates/candidate/profile.html | unsafe and disabled | React-only root removed from active template and retained in checkpoint; recover parent legacy form. |
| app/frontend/templates/recruiter/search.html | unsafe and disabled | React-only root removed from active template and retained in checkpoint; recover parent legacy form. |
| app/package.json | reusable after correction | Retain reviewed dependencies; add explicit build:wip script; production build remains legacy. Existing dependency ranges are preserved, not upgraded. |
| app/package-lock.json | reusable unchanged | 248 package entries inspected; all non-link dependencies have integrity hashes; React 19.1.1/Tailwind 4.1.14 locked. npm audit reports zero known vulnerabilities. |
| app/tsconfig.json | reusable unchanged | JSX and TSX checking retained; no narrowing of original TypeScript or mypy scope. |
| app/vite.config.ts | reusable after correction | Production compiles legacy without Tailwind plugin; mode wip compiles only React/Tailwind entry into static/dist/wip. Separate manifests/assets and DOM ownership. |

An additional fallback startup correction defers existing legacy draft restoration to a microtask. Module dependency evaluation could otherwise run its add-criterion loop before the search renderer registered the click handler, hanging a restored page. A focused browser regression covers two restored criteria and the retained prompt. Storage semantics are unchanged; migration away from legacy session storage remains an explicit later-slice obligation.

## Route controls and rollback

`FRONTEND_REACT_ROUTES` in server settings is an empty dictionary by default, keyed by resolved Django URL name. A strict boolean true also requires an entry in the code-reviewed `VERIFIED_REACT_ROUTES` registry. That registry is empty for FM1: even an accidentally true flag cannot serve WIP. Query parameters and cookies cannot enable React.

The shared base selects exactly one content template, script and stylesheet. Existing authorization executes before rendering; the context processor makes no authorization/database decisions. Future verified React templates must be content fragments and supply their own exclusive assets. Unit tests use a synthetic test-only registration to exercise cutover and rollback; no actual route is registered.

Rollback: set the route flag false/remove it, apply server configuration and reload the existing URL. The legacy content and assets return; no data or URLs change, and no mutations are replayed. The WIP preview is a build/test artifact, never a production page. Run production build before build:wip because the normal clean build replaces static/dist; the preview recreates its own subdirectory.

## Baseline procedure and current differences

The capture test is `app/tests/browser/fm1-baselines.spec.ts`; screenshots and manifest live in `fm1-baselines/` alongside this report. Existing local one-time recruiter/candidate/Tenant Admin bootstrap commands create authenticated synthetic sessions. APIs are real for production captures; no mocked API responses are used. Test-only reference context uses the exact external HTML bytes and blocks remote fonts for repeatability. In-memory viewport/zoom/screen activation never edits the original file.

Each captured state has 1440×1000, 1024×768, 390×844, 320×844 and 1440×1000 at CSS zoom 200% images. CSS zoom is an automated reflow approximation, not a completed manual browser-zoom/screen-reader certification. Existing browser tests cover keyboard, dialogs and axe; manual assistive-technology review remains a distinct gate.

Production captures: search home, criteria review, results, detail dialog, management/disclosures, comparison, organization, candidate profile/resume, role/application, progress, rights, governance and audit. Additional denied direct-navigation state is retained. Mockup captures cover chooser, candidate platform, search home/sidebar, results, detail/notes/action and comparison. Dormant publicProfile/interp/admin sections are explicitly labeled as dormant reference captures: its script redirects interp/profile/admin routes, so these are not evidence of working mockup navigation.

Intentional current differences:

- Legacy system fonts, teal controls, plain form layout and wider fieldsets differ substantially from paper/navy cards, sidebar/chips and display typography. This is a baseline, not a visual-parity claim.
- Production includes visibility/audience consent, field-scope disclosure, confirmation, eight candidate statuses, scan state, rights controls and redacted governance missing from the mockup; those controls must survive later slices.
- Production comparison is deterministic and informational. Demo scores, direct mailto/WhatsApp actions, local demo storage and fake verification are not approved implementation behavior.
- The current public chooser/jobs directory does not exist yet. These remain FM3/FM10 scope; no new route is introduced in FM1.
- No approved logo/local font assets were found. The reference requests missing enter-logo-blue.jpeg (404); remote fonts are blocked in new reference captures. Record the broken-logo reference appearance; later pages use the approved temporary text wordmark/local metric fallbacks.
- Existing authenticated candidate-management HTML requires X-Tenant-ID, while its ordinary anchor navigation omits that header and receives 403. Capture this failure separately; capture the authorized page with the explicit tenant header, still subject to server membership checks. Backend correction is outside FM1 and remains a blocker to calling the full legacy navigation flow verified.
- Repeated search in the shared development database failed when six-entry recent eviction attempted to delete a SearchDefinition referenced by CandidateWorkRecord.originating_search (PROTECT). Existing code at app/modules/search/views.py:126 raises ProtectedError. No backend workaround or deletion was applied. Final captures and authenticated regression runs used separate fresh synthetic databases so this defect remains visible as a limitation, not mistaken for a solved regression.
- Existing sessionStorage-backed criteria/selection remains legacy behavior; the approved no-protected-browser-storage requirement must be satisfied by later replacements. FM1 does not introduce new protected persistence or port it to React.
- Automated live-page audit records moderate landmark findings in results/comparison and nested/duplicate main landmarks in criteria review; the denied Django 403 also lacks main/region landmarks. No serious/critical finding appeared in the captured normal pages. These are documented baseline defects, not approved permanent accessibility exceptions.

## Verification results

| Check | Result |
|---|---|
| Legacy production build | PASS: 25 modules; app.js/app.css excludes React and Tailwind |
| Isolated WIP build | PASS: 27 modules; separate static/dist/wip output; incomplete controls remain disabled |
| Complete PostgreSQL suite | 273 passed, 1 expected skip (database trigger prevents tamper fixture); full suite run once |
| Collection | 274 tests, versus prior 269; five rollout tests added |
| Repository-wide mypy . | PASS: 213 source files; prior scope preserved |
| Ruff check / format --check | PASS, 213 files formatted |
| TypeScript / ESLint / Prettier | PASS |
| Django system / migration checks | PASS, no model drift or unapplied migration in isolated database |
| npm audit | Zero known vulnerabilities |
| Complete existing non-authenticated browser/accessibility suite + FM1 isolation | 35 passed |
| Existing authenticated recruiter/search, comparison, application/status, governance | All five scenarios passed with separate one-time sessions |
| Baseline capture | 26 states × five viewport/zoom configurations = 130 PNGs; manifest includes live axe findings |
| Default flags, unverified enable attempt, template/assets exclusivity and rollback | Five unit tests passed; no client flag can enable WIP |
| Mockup preservation | Both external and repository SHA-256 unchanged |
| Previous tests / typing scope | No deleted tests, no narrowed configuration |

The authenticated search test initially failed because it clicked the first result but asserted employment evidence belonging to a specific candidate. Its selector now targets the named candidate card; every original assertion remains. The focused rerun passed. No production ordering/scoring was changed. The isolated WIP preview is build/DOM-isolation verified, not feature acceptance approved.

The exact suites were run in batches: non-authenticated Playwright once, then each existing authenticated spec with fresh bootstrap URLs (the search and comparison specs otherwise share one single-use environment token). Only failed focused checks were rerun. Baseline harness development reruns did not rerun the complete PostgreSQL suite.

## Reproduction and retained resources

Run from app with existing local services. Final captures used DATABASE_URL pointing to enter_fm1_baselines_20261001, VALKEY_URL database 8 and a Django --nostatic server on 8002. Authenticated regression used enter_fm1_browser_20261001, Valkey database 9 and port 8003. Both contain synthetic fixtures only and are retained for review; no existing development records were deleted. --nostatic lets the repository's explicit static URL handler serve the existing Vite output. No server configuration file was changed for these test processes.

```sh
npm run build
npm run build:wip
# With the isolated Django server/configuration above:
FM1_CAPTURE=1 FM1_ORIGIN=http://127.0.0.1:8002 npx playwright test tests/browser/fm1-baselines.spec.ts --workers=1
# Reference-only refresh does not touch backend data:
FM1_CAPTURE=1 FM1_REFERENCE_ONLY=1 npx playwright test tests/browser/fm1-baselines.spec.ts --workers=1
npx playwright test --grep-invert authenticated --workers=2
# Issue fresh existing bootstrap commands for each authenticated spec.
```

Use a clean, isolated synthetic database for a new baseline set. Date/UUID text may vary across newly seeded databases; retained PNGs are the reviewed capture set, not permission to silently replace goldens. Remote font differences, missing logo and dormant screens are explicitly documented. Manual assistive-technology and actual browser UI zoom certification is not claimed by CSS zoom/axe.

## Initial FM1 disposition (superseded by authorized remediation below)

- FM1-01: complete baseline/test inventory and capture evidence.
- FM1-02: complete checkpoint classification, corrected legacy fallback, disabled WIP, default-off route controls and verification.
- FM1-03: blocked final acceptance. Although requested automated suites pass, the live direct-navigation denial, protected search-eviction failure and outstanding manual accessibility review prevent an unconditional verified-fallback signoff.

FM2 is not approved to begin under the sequential gate. Resolve or explicitly disposition these existing defects with authorized follow-up scope first. No production React cutover, FM2 work or Phase 10 work occurred.

## Authorized FM1-03 remediation and final signoff — 2026-10-01

The preceding results and defects describe the initial checkpoint. This section supersedes its blocked disposition. Only the explicitly authorized FM1 fixes were made; API contracts, database models/migrations, RLS policy, role policy and React rollout configuration were not changed.

### Tenant context and navigation

Root cause: the HTML candidate-management view required middleware tenant context supplied by `X-Tenant-ID`, but ordinary anchor/direct navigation cannot supply that API header. The route now uses the existing trusted Django membership/RLS lookup to authenticate the session, validate the route tenant and recruiter/hiring-manager role, and emit tenant bootstrap data. A conflicting header still fails closed. The shared membership lookup also explicitly requires an active tenant.

`frontend/shared/tenant-client.ts` centralizes same-origin, tenant-path, cookie and CSRF transport for candidate-management and disclosure calls. No shared fetch abstraction existed previously; the existing request conventions are preserved in this small helper. Its bootstrap value is transport context, never an authorization decision or user-controlled tenant selector. Object/field authorization remains in the existing APIs.

New contract tests reproduce the former failure and cover same-tenant HTML, unauthenticated/cross-tenant/mismatched-header/tenant-admin/revoked-membership denial. Updated real-browser capture verifies direct navigation, refresh and browser Back without injected headers. Manual keyboard navigation followed the actual search → detail dialog → Manage this candidate link and confirmed the authorized summary loaded.

### Recent projection and provenance

Root cause: recent eviction bulk-deleted search rows beyond six, including `CandidateWorkRecord.originating_search` references protected by `PROTECT`. Cleanup now bounds the six-item unexpired, unsaved, actor/tenant-specific projection using the existing `expires_at` field. An old referenced search is expired from recents but retained intact for authorized provenance; neither the work record nor its FK is detached or overwritten. Unreferenced expired/evicted ad-hoc searches remain evictable. Explicitly saved searches are excluded and remain reopenable under existing owner/tenant authorization even after recent expiry. No new model state is necessary.

Cleanup locks only the search row (PostgreSQL `FOR UPDATE OF self`, not the nullable saved-search join); the FK stays protected and a protected deletion is rolled back to a savepoint. New tests execute eight searches, retain old work provenance, evict an unreferenced search, reopen an expired saved search and reject cross-tenant access. Immutable audit events and their retention controls are unchanged. Repeated live capture and regression now run against the retained database containing prior CandidateWork, rather than avoiding the defect with fresh data.

### Accessibility remediation and manual checklist

Embedded informational findings in results/comparison are labeled groups, not nested complementary landmarks. The criteria editor is a named section. Criteria review no longer nests a second main within the base main. The shared base provides one focusable main and a first keyboard skip link; denied HTML has a safe 403 template with a heading and main. No content disclosure is added to errors.

Reviewed in Chrome on macOS using native keyboard actions, screenshots and the accessibility tree:

| Checklist | Result / scope |
|---|---|
| Main and navigation landmarks | PASS: one main on each captured production state; result navigation has its distinct `Result filters` name; no duplicate navigation region introduced |
| Heading hierarchy and control names | PASS: search H1 → sections H2 → candidates H3; management H1 → workflow sections H2; native tree exposes labels, checkbox values and select state |
| Skip links and keyboard order | PASS: first Tab focuses visible main skip link; Enter targets active main; subsequent Tabs reach results shortcut, sign-out and prompt; management order reaches Back, note input/button and status select |
| Focus and dialogs | PASS: visible outlined links/selects; detail dialog exposes its name, evidence, management link and Close; Tab remains in modal interaction and Escape returns to invoking details button |
| Async feedback | PASS: real result count and loaded candidate context appear in existing live-status regions; browser regression covers safe errors/conflicts and disclosure feedback |
| 320px reflow | PASS: reviewed current 320px capture including complete management/disclosure form; existing responsive/keyboard tests pass |
| Actual browser zoom | PASS: native Chrome zoom popup verified 200%; management headings, overview and keyboard-focused workflow controls remain readable/reachable; reset verified at 100% afterward |
| Screen-reader-oriented review | PASS for exposed roles, labels, headings, state and focus order in native accessibility tree; this is not a claim of VoiceOver/NVDA speech-output testing or a production-wide AT certification |

Current manifest has **zero axe violations on every captured production state**. Capture now fails for any moderate/serious/critical finding and requires exactly one main. Existing automated accessibility, dialog, conflict, keyboard and responsive tests also pass. This signs off the requested FM1 manual keyboard/screen-reader-oriented checklist, not the later production-hardening accessibility gate.

### Temporary branding and baseline differences

Approved fallback: text wordmark **“enter”**, local/system sans stack, Georgia-compatible display fallback, system monospace fallback. No remote fonts, invented logo or redrawn logo. Missing approved assets are a recorded visual difference, **not an FM2 blocker**. Future semantic `font-sans`, `font-display`, `font-mono` tokens and the wordmark boundary must allow asset substitution without component restructuring; no FM2 component was implemented here.

The refreshed manifest contains 26 current states × five configurations = 130 current images. Five historical `production-management-direct-navigation-denied-*` images are retained as defect evidence but are no longer current manifest entries. The new `production-management-direct-navigation-*` set demonstrates the fix. Audit/governance/organization captures include additional real synthetic audit/review records accumulated by verification; dynamic audit timestamps and the mockup's generated admin timestamp explain those content differences. Other baseline layout differences listed above remain intentional until migration. The original reference bytes and hash are unchanged.

### Final verification

| Check | Follow-up result |
|---|---|
| Complete PostgreSQL suite (once after fixes) | **275 passed, 1 expected trigger-fixture skip**, 276 collected; two regression tests added, none removed |
| Repository-wide `mypy .` | PASS, **215 source files**, original scope unchanged |
| Ruff lint / format | PASS, 215 files |
| Django system / migration drift / applied migrations | PASS, no schema changes |
| TypeScript / ESLint / Prettier | PASS |
| Legacy / isolated React-Tailwind Vite builds | PASS, 26 / 27 modules |
| Complete non-authenticated browser/accessibility + Tailwind isolation | **35 passed** |
| All existing authenticated scenarios | **5 passed**: recruiter search, comparison, application/publication, Tenant Admin governance, recruiter organization |
| Updated authenticated baseline capture | **1 passed**, direct/refresh/Back and live axe checks included |
| Default-off / rollback / exclusive renderer tests | PASS within full PostgreSQL suite; empty verified registry and default flags unchanged |
| Original mockup | Both copies remain SHA-256 `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9` |
| Prior tests | No test files or test cases removed; full prior suites retained |

Final status: **FM1-01, FM1-02 and FM1-03 complete. FM2 dependency gate cleared, but FM2 not begun.** All production routes remain legacy; no React feature route is registered/enabled. Rollback remains the default-off server-controlled mechanism described above. No outstanding FM1 blocker; missing brand assets and deliberate legacy visual differences remain documented migration inputs.
