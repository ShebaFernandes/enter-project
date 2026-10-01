# FM5 criteria-review verification — 2026-10-01

Scope: FM5-01 → FM5-02 → FM5-03, depending on completed FM4-03. FM1–FM4,
including FM3/FМ4 remediation tasks, remain complete. The FM1–FM14 umbrella
gate remains unchecked. No FM6 or Phase 10 implementation is included.

## Implementation and boundaries

Only `/tenants/{tenant_id}/recruiter/search/criteria-review/` is added to the
React renderer registry, under `criteria-review-page`. The flag is absent/off in
both the base policy and current local settings. Existing locally enabled chooser
and search-home flags were not changed. False/absent flags or missing React assets
render the existing template at the same URL; rollback changes no data or handoff.
Verification enabled the flag only in a separate process on port 8016.

`CriteriaReview`, `GroupEditor`, `CriterionEditor` and `ImpactSummary` reuse FM2
AppShell, Field, input/select, Button, Chip, Alert, Loading, EmptyState, status and
ConflictPanel primitives. Styles are scoped beneath `.enter-ui` and use FM2 tokens;
no reset/preflight, remote assets or imperative legacy renderer is loaded into this
subtree. The legacy review file/template remain unchanged.

Django membership/role checks are unchanged. Escaped bootstrap supplies tenant and
page context; the mount infrastructure checks the active session. The same-origin
client supplies credentials, CSRF and trusted tenant context. Existing encrypted
CRITERIA_REVIEW GET/PATCH operations restore and revise with If-Match; they retain
all actor/session/tenant/opening/version/expiry checks. No new API/model/migration,
AI call, authorization rule, scoring or deterministic search logic is introduced.

Group/criterion IDs survive edits and moves. ANY/ALL, requirement/preference/
exclusion, all existing fields/operators, typed values and result limits remain
editable. Estimates are debounced and serialized; response estimates never replace
newer local edits. Confirmation waits for a server-accepted revision, then uses the
existing search POST and SEARCH_RESULTS handoff to enter **legacy** results.
Results, detail, comparison, candidate and governance routes are untouched.

409 re-reads currently authorized state, retains the attempted draft and requires
discard, explicit merge or explicit resubmission. Denial/expiry clears displayed
criteria and offers a safe return. Validation, throttling and degraded responses
retain editable drafts. Refresh restores only server-accepted edits, with an explicit
notice; it never executes a search. Skip-link focus preserves the opaque fragment.

Confirmed execution is not blindly retried after an uncertain network/5xx outcome:
the existing search API has no idempotency contract. Once a search ID is received,
opening-results retries use the **same handoff idempotency key**, without another
search POST. This is a deliberate safe limitation, not a backend contract change.

No criteria, prompt, candidate data, tenant context, token or return URL is written
to browser storage. Only the existing opaque fragment transport is used. No logging
of protected state is added. Final results/comparison authorization stays server-side.

## Tests and evidence

Test-first route coverage failed before implementation because React review did not
exist. Added tests are:

- `app/tests/contract/test_fm5_route.py`: flag-off/on/rollback, escaped bootstrap,
  no-store, exclusive bundles, role denial and always-legacy results.
- `app/tests/browser/fm5-review.spec.ts`: stable IDs and human edits, explicit-only
  execution, ANY/ALL, edits/moves/removals, empty state, focus, expiry, 409, validation,
  throttle/degradation, safe retries, typed list/false values and storage inspection.
- `app/tests/browser/recruiter/fm5-authenticated.spec.ts`: fresh synthetic login,
  React home → React review → legacy results → comparison → return; accepted-edit
  refresh, responsive/zoom captures, accessibility and empty protected storage.
- A new deterministic test-only HTML fixture and five screenshot assertions.

Existing tests are retained. Only the bootstrap helper gained an FM5 origin branch;
its synthetic-only, isolated-cache throttle reset restrictions are unchanged. The
complete existing security suite still exercises protected-attribute/injection
rejection, source visibility, consent, RLS and session-bound handoff isolation.

| Final gate | Result |
|---|---|
| Fresh PostgreSQL complete suite | 347 passed, 1 existing skip; 348 collected; 22.46s |
| Existing skip | PostgreSQL audit trigger prevents constructing the tampered fixture |
| Repository-wide `mypy .` | 231 source files, no issues |
| Ruff format/lint | Passed, 231 files |
| Django check / migration drift | No issues / no changes detected |
| TypeScript, ESLint, Prettier | `npm run check` passed |
| Vite | Legacy, React, WIP, showcase builds passed; final React rebuild passed |
| Complete Playwright | 70 passed, zero skipped, 1.6m; all gated authenticated scenarios enabled |
| Accessibility / isolation | Zero serious/critical FM5 axe violations; existing isolation, keyboard and rollback tests passed |
| Original mockup | Both copies retain SHA-256 `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9` |

The initial full PostgreSQL invocation inherited the user's locally enabled
chooser/search flags, causing two existing legacy-default expectations to fail.
The entire suite was rerun with `settings.FRONTEND_REACT_ROUTES = {}` before
`pytest.main(["--ds=config.settings.local", "-q"])`, matching base production
defaults. Tests still individually exercise flag-on and rollback. No test or local
setting was weakened/changed to achieve the pass. No `--reuse-db` was used.

Python verification uses PostgreSQL `enter` and Valkey DB 10. Browser verification
uses the existing synthetic `enter_fm4_verify_20261001` database/Valkey DB 11 and
fresh one-time URLs. Legacy server 8014, FM4 flag-on server 8015 and FM5 flag-on
server 8016 run `--nostatic`; all four builds finish before suites start.
The browser command sets LOCAL_AUTH_ORIGIN, FM4_AUTH_ORIGIN, FM5_AUTH_ORIGIN,
FM1_ORIGIN, FM3_ORIGIN, FM1_CAPTURE=1 and guarded LOCAL_AUTH_RESET_THROTTLE=1.
FM1_OUTPUT and FM3_LIVE_OUTPUT target `fm5/regression-baselines`; no previous
baseline assertions are replaced. See the [screenshot manifest](fm5/screenshot-manifest.md).

## Accessibility and visual review

Keyboard-oriented checks verify skip → main without losing the handoff, native
controls and labels, focus on newly added/moved criteria, focus after removal,
explicit submit, focus on conflict recovery and safe return navigation. One active
main landmark, logical h1/h2/fieldset structure and polite async/error announcements
are retained. FM2 focus styles and reduced-motion behavior are inherited.
No new dialog is needed; the existing explicit conflict panel is reused.

Screenshots cover 1440×1000, 1024×768, 390×844, 320×844 and 1440×1000 at 200% zoom.
Automated checks assert no horizontal overflow and zero serious/critical axe
violations. Desktop and 320px screenshots were visually inspected against the
immutable FM1 `#interp` reference. This is automated accessibility-tree/keyboard
verification, not a claim of testing a live screen-reader product.

Intentional differences: temporary text wordmark/system/Georgia fonts; no retained
raw prompt or fabricated career timeline; explicit multigroup field editors instead
of mockup-only free-text chips; visible privacy/refresh/conflict/retry controls;
real server estimates and result limit. The centered 880px paper/raised review panel,
hairline borders, restrained shadow, semantic accents and serif headings retain the
mockup's visual direction. Missing approved logo/font assets are not a blocker.

FM5-01, FM5-02 and FM5-03 are complete after the final full browser rerun.
No remaining FM5 blocker. FM6's dependency is cleared, but FM6 has not started.
No production route flag was enabled.

## Files changed

- `app/frontend/react/criteria-review.tsx`, `criteria-review.css`, `entry.ts`.
- `app/frontend/templates/recruiter/react_criteria_review.html`.
- `app/modules/search/page_views.py` (bootstrap only) and
  `app/modules/operations/frontend.py` (route registry only).
- The new FM5 contract/browser tests, deterministic fixture and screenshot
  assertions listed above; `app/tests/browser/local-bootstrap.ts` (origin selector).
- `specs/001-recruiter-candidate-workflows/tasks.md`, this evidence, screenshot
  manifest and captures beneath `docs/evidence/frontend-migration/fm5/`.

No models, migrations, existing APIs, authorization services, legacy feature
implementations or original mockup files changed. No prior test was removed and
the mypy scope was not narrowed.
