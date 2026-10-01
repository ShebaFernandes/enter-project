# FM3 — public entry and public-opening security clarification

Verified 2026-10-01. Scope: FM3-01 → FM3-02 → FM3-03 only, dependent on completed
FM2-03. FM1/FM2 remain complete. FM4 and Phase 10 were not started. The FM1–FM14
umbrella acceptance item remains unchecked.

## Approved clarification and threat review

The owner explicitly authorized a separate public projection and migration after
inspection confirmed source openings have forced tenant-only RLS. Anonymous
source queries are forbidden. The original source RLS migration and policies are
unchanged. This clarification is recorded in plan.md, data-model.md, tasks.md,
frontend-migration.md, the authorization matrix and the public OpenAPI schemas.

New models in `modules/recruiting/models.py` and migration
`0013_public_opening_projection.py`:

- `PublicOpeningProjection`: independent public UUID, title, public description,
  location text, work arrangement, employment type, publication timestamp,
  optional closing timestamp, and internal active marker. No source/tenant FK,
  candidate data, teams, notes, scores or private contact fields.
- `OpeningPublicationLink`: private source/public UUID/tenant association. It is
  never serialized. Tenant-scoped writer access and an exact transaction-local
  public-ID read scope support the authenticated application resolver.
- Public SELECT policy requires active, already-published and non-expired rows.
  Both new tables have forced RLS. No SECURITY DEFINER function was introduced.
- `enter_public_openings_reader` is NOLOGIN, NOINHERIT, NOSUPERUSER and
  NOBYPASSRLS, with SELECT only on the projection. The endpoint switches to this
  role even on the superuser development connection. It cannot read source/link
  tables or INSERT/UPDATE/DELETE projections.
- `enter_opening_publisher` is a database capability role, not a sixth product
  role. It supports tenant-scoped synchronization; all five application roles
  and existing authorization decisions remain unchanged.

Migration execution requires permission to provision the two database roles (or
safe pre-provisioned roles). It grants them to the migration connection role. If
the deployed runtime uses a different role, provision its membership explicitly;
do not grant table access to SQL PUBLIC or use a BYPASSRLS runtime. Missing reader
membership produces a safe unavailable response, not an unrestricted fallback.
No production deployment or broad database grants were performed here. The
migration was applied only to ephemeral test databases and the existing isolated
synthetic verification database. Role objects are not dropped on reverse
migration because they may be shared by another database.

## Publication lifecycle and public API

`openings.update_opening` retains existing authorization/validation and invokes
transactional synchronization for explicit state publication or an already-public
record. Ordinary edits to a previously private OPEN record do not publish it.
Synchronization rereads/locks the authoritative opening and current active
membership and checks existing opening-write tenant/object scope. OPEN publishes;
PAUSED/CLOSED withdraw. Existing records are not automatically backfilled.

SECURITY INVOKER triggers deactivate publication before any source UPDATE/DELETE
and before private-link deletion, including ORM cascade order. Authorized public
updates replace the allowlisted projection in the same transaction. A source,
projection or audit failure rolls the transaction back. No newly private state
commits with an old active projection. `closes_at` is enforced on every public
read; optional company, experience and skill publication fields are omitted
because no explicit source publication configuration exists. There is no new
ARCHIVED source enum: existing PAUSED/CLOSED lifecycle states are unavailable.
Publication and withdrawal service actions record minimized audit metadata, not
job descriptions or candidate values. Direct database maintenance remains outside
the application authorization/audit workflow; invalidation triggers still prevent
stale public visibility.

`GET /api/v1/public/openings` and `GET /api/v1/public/openings/{publicUUID}` use
only the restricted projection reader. Responses contain exactly:
`id`, `title`, `description`, `location`, `work_mode`, `employment_type`,
`published_at`, `closes_at`, `application_url`.
The active marker, tenant and source IDs are not serialized. Location JSON is
never copied wholesale. Public role URLs derive from the public UUID.

Pagination is public-UUID ascending, default 25, maximum 100, with no private
counts. Public reads share a 60/minute network throttle, fail closed on limiter
failure and use `Cache-Control: no-store`. Missing, private and withdrawn IDs
produce the same unavailable result. The approved detail schema was corrected
from the internal Opening schema to the public allowlist.

`/roles/{publicUUID}/` first checks the live projection. Only authenticated
candidates resolve its private link, then existing source state, consent,
candidate-owned clean resume, duplicate submission and notification validations
run. Existing authenticated internal-ID API callers remain consent-bound and
compatible. URL **patterns** are preserved; old internal-ID public links now
return 404 rather than disclose internal IDs. Authorized publication supplies a
new independent public link. The local synthetic bootstrap now supplies that
public link, without changing its one-time token or production guards. The
legacy application renderer consumes the minimized location text through safe
text nodes rather than HTML interpolation.

## Frontend, rollout and recovery

`/` has a real Django chooser fallback and a React `PlatformChooser`/`PublicShell`
using the FM2 Header, Wordmark, SkipLink, Alert and StatusMessage primitives.
Recruiter navigation goes directly to the existing `/api/v1/auth/login` PKCE
entry; no email/password collection or authentication bypass is added. Candidate
navigation reaches the real projection-backed `/jobs/` directory, whose minimal
Django implementation stays legacy until its later visual slice.

Only `platform-chooser` is registered for React. `FRONTEND_REACT_ROUTES` remains
`{}` in repository settings. No existing workflow route is registered/enabled.
An explicit server boolean opts in the chooser; missing manifest/assets or false
flags select legacy. Removing/disabling the flag rolls back at the same URL,
without database rollback or mutation replay. Bundle failure retains accessible
secure sign-in/jobs links. Escaped JSON bootstrap carries only page/version/
session-required and an optional generic entry-error flag. Provider/account error
details are never reflected. React does not read cookies or browser storage.

The foundation exports now live in side-effect-free `foundation.ts`; importing
shared components into the FM2 showcase cannot mount a production page. The
production entry alone registers the chooser. Tailwind preflight remains absent,
selectors remain scoped, and namespaced theme tokens are emitted statically so
the separate chooser stylesheet can use the approved shadow token. Legacy and
React never share ownership of a mounted subtree.

Live rollback drill: restarted the isolated server at the same
`http://127.0.0.1:8002/` with unchanged default-off settings. The page returned to
legacy assets and identical sign-in/jobs destinations. Public response SHA-256
before and after was
`6404fa80f5716949693d1bb3eb6524e76ef5b22f7a63825760865cdd7b15af69`.
This hash describes synthetic verification data, not a production data fixture.

## Visual and accessibility signoff

Reference: immutable mockup `#login`, including its later 520px-card polish
overrides, and FM1 `mockup-chooser-*` baselines. Captures cover 1440×1000,
1024×768, 390×844, 320×844 and 1440×1000 at 200% CSS zoom. See the adjacent
[screenshot manifest](fm3/screenshot-manifest.md).

Intentional differences:

- Approved lowercase text wordmark replaces the missing image asset; local/system
  sans, Georgia-compatible display and system monospace remain the font fallbacks.
  No remote fonts or invented logo. Display-font metrics can change heading wraps.
- Secure OIDC explanation replaces the mockup's demo email credential field.
  Copy does not promise automatic ranking or an unimplemented upload journey.
- Choices are real links, with visible focus and navigation announcements.
- Jobs is the minimal real-data legacy destination, not the mockup's full public
  profile/directory styling. That visual slice remains FM10, not FM4 work.
- Strong visible focus is retained instead of the mockup's weaker outline.

Manual keyboard and screen-reader-oriented DOM review on the live page verified:
one visible main, one H1, named Platform choice navigation, skip-link focus on
`#main`, order Wordmark → Recruiter → Candidate, visible 3px sage outline,
keyboard activation of real jobs navigation, Back restoration, and no clipped
controls at 320px (scrollWidth/innerWidth both 320; card width 288). The status
region and generic alert are exposed with the expected roles. No dialog is added
in FM3; existing dialog focus/return tests still pass. This is keyboard/semantic
review, not a claim of a speech-output screen-reader certification.

FM3 chooser and jobs axe scans report **zero violations** at tested viewports;
no serious/critical findings. Reduced-motion behavior adds no entry animation.
The safe error/loading and bundle-recovery fixture also passes. All existing
accessibility tests and the authenticated FM1 recapture pass.

## Verification results

| Gate | Result |
|---|---|
| Test-first | Missing projection import failed first; new directory/route tests returned 404 before implementation; chooser tests failed before mount implementation |
| PostgreSQL collection | 295 tests, up from 279; no prior test functions removed |
| Complete PostgreSQL regression | **294 passed, 1 expected skip**, 15.01s; skip is the existing audit-trigger tampering fixture |
| Restricted-role tests | Reader non-owner/non-BYPASSRLS confirmed; source/link read and projection mutations denied; expired/inactive hidden; cross-tenant writer denied; source policy remains tenant_isolation with forced RLS |
| Repository-wide `mypy .` | PASS, 222 files; scope/configuration not narrowed |
| Ruff lint/format | PASS, 222 files formatted |
| Django checks / migration drift | PASS / no changes detected |
| TypeScript / ESLint / Prettier | PASS |
| Vite legacy / retained WIP / React / showcase | PASS, 27 / 27 / 32 / 30 modules |
| Browser collection | 53 tests in 20 files, up from 48 |
| Complete non-authenticated browser suite | **47 passed**, including live FM3 OIDC handoff with external HTTPS blocked |
| Existing authenticated journeys | **5 passed**: recruiter search, comparison, candidate application/status, Tenant Admin, recruiter organization |
| Existing authenticated FM1 capture | **1 passed**, 130 refreshed captures in `app/test-results/fm1-fm3-verification`; approved FM1 images untouched |
| Rollout/rollback and Tailwind isolation | PASS |
| Original mockup | Both copies unchanged: SHA-256 `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9` |

One pre-existing public-opening test was retained and strengthened to require the
new public ID and reject tenant/business-unit fields, matching the explicit
security clarification. No previous test files/functions or visual baselines were
deleted. No authentication, candidate permission, source RLS or model behavior was
weakened. Complete PostgreSQL regression was run once after focused fixes; browser
regression ran in the existing non-authenticated/authenticated/capture batches.

FM3-01, FM3-02 and FM3-03 are complete. FM4's dependency gate is clear but FM4 has
not begun. Remaining operational considerations are explicit runtime role
membership, authorized publication of existing OPEN records, and the approved
temporary brand/font difference; no frontend route is enabled by default.
