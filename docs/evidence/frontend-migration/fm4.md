# FM4 completion verification — 2026-10-01

Scope: FM4-01–03 and FM4-R01–R06 only. FM5 has not started. FM1–FM3 and
FM3-R01–R03 remain checked; the FM1–FM14 umbrella remains unchecked.

## Implementation

`SearchHome` in `app/frontend/react/search-home.tsx` owns the home composer,
authorized opening selector, suggestions, speech lifecycle and projects/recents/
saved-search panel. It reuses FM2 Header, Button, SkipLink, Alert and StatusMessage,
semantic Tailwind tokens and the shared same-origin CSRF client. Bootstrap comes
from escaped Django JSON. No client-only authorization or business parsing exists.

`recruiter-search-page` is registered, but its server flag remains default-off.
`?view=results` always selects legacy, even with the home flag on. Review, detail
and comparison are not React routes. Each renderer loads only its own bundle and
owns its own subtree. Removing/setting the flag false restores the same-URL legacy
home immediately without data changes. Missing React assets also fail to legacy.

The existing encrypted SearchWorkflowHandoff and migrations 0006/0007 were reused;
no further migration was added. Criteria, results and comparison keep distinct
target kinds, hashed random tokens, actor/tenant/session binding, fifteen-minute
expiry, forced RLS, current source checks and minimized audit events. Comparison
remains read-only with respect to Application/CandidateWork/shortlist/status.

Recent collection/detail return allowlisted owned, authorized, unexpired ad-hoc
records, at most six. Seven-day expiry and CandidateWork provenance remain intact.
Active handoff sources survive recent cleanup. Recent/saved reopen validates the
source and creates a fresh review checkpoint without AI or browser persistence.

Search execution retains the complete deterministic ordered snapshot-reference
set. New page tokens identify cumulative display boundaries without copying result
records or executing another search. Display freshly rechecks visibility/consent.
Fragment navigation reloads through Django, so pagination, refresh and Back restore
server state. Comparison return derives a safe page containing selected references.
Legacy estimate updates are serialized before confirmation to avoid self-induced
ETag races; real cross-tab stale writes remain rejected.

## Acceptance coverage

- `test_search_handoffs.py`: encryption/hash-only storage, retry bounds, session/
  actor/tenant/target binding, expiry/completion/revocation, ETags, CSRF, no-store,
  rate limits, minimized audit/log output, non-owner/non-BYPASSRLS forced RLS.
- `test_comparison_handoffs.py`: ordered selection, limit, source membership,
  hidden candidates, type isolation, stale writes, safe server return, no recruiting
  side effects, restricted-role RLS and session revocation.
- `test_fm4_remaining.py`: recent reopen, active source retention, other-owner
  denial, fresh opening-state/scope checks, default/flag-on/legacy-result renderer,
  stable persisted pagination and return to the selected candidate's page.
- Existing FM1 provenance, search authorization and final comparison authorization
  tests remain present and run in the complete PostgreSQL suite.
- FM4 browser tests cover editable/non-auto-submitting speech, unsupported speech,
  validation, interpreting, degraded/rate-limit/sidebar failures, empty states,
  responsive screenshots, keyboard Escape/focus return and accessibility.
- Authenticated journeys use fresh one-time URLs per test, including React home →
  legacy review → results → comparison → return, recent reopen, refresh, pagination,
  Back/Forward, sign-out/history protection and empty local/session storage.

Existing test cases were not deleted. The old authenticated search test's explicit
sessionStorage setup was replaced with actual confirmation and bound restoration;
its evidence/detail/sign-out/history assertions remain. No mypy scope was narrowed.

The verification database is `enter_fm4_verify_20261001`, with Valkey DB 11. The
bootstrap test helper optionally clears only the synthetic actor's handoff throttle
key between scenarios, guarded by the verification DB name and exact isolated cache
URL. This avoids one scenario exhausting another's allowance; production throttles
and the dedicated rate-limit assertions remain unchanged. All builds finish before
suites start, because the legacy build intentionally clears its output directory.

## Visual and accessibility review

See [screenshot manifest](fm4/screenshot-manifest.md). Four required viewports and
200% zoom are captured for both deterministic and authenticated contexts. The
keyboard-oriented checks cover labeled composer/selector, native button activation,
skip/main, visible focus, modal Escape/return and async status/alert semantics.
Axe serious/critical findings must be zero. Automated accessibility-tree/keyboard
verification is not represented as a live screen-reader product certification.

## Final gates

| Gate | Final result |
|---|---|
| Complete PostgreSQL, fresh pytest DB | 345 passed, 1 skipped; 346 collected, 21.69s |
| Existing skip | Audit tamper fixture cannot be constructed because the PostgreSQL trigger rejects it; not an FM4 skip |
| Complete Playwright | 60 passed, zero skipped, 1.4m; all environment-gated scenarios enabled |
| Accessibility | Zero serious/critical violations in required FM4 scans; legacy/FМ1/FМ2/FМ3 accessibility gates also passed |
| Repository-wide `mypy .` | 230 source files, no issues |
| Ruff format/lint | 230 files formatted; all checks passed |
| Django checks/migration drift | No issues; no changes detected |
| TypeScript/ESLint/Prettier | `npm run check` passed |
| Vite | Legacy, React, WIP and showcase builds passed sequentially before verification |
| Rollout/isolation | Flag-on home, flag-off fallback, always-legacy results and existing Tailwind isolation tests passed |
| Browser storage | Both stores empty in authenticated handoff/comparison/pagination journeys |
| Preservation | No prior test cases deleted, no mypy narrowing, no original mockup changes |

Commands run from `app/`: `pytest --ds=config.settings.local -q` with the local
PostgreSQL DSN and no reuse-db option; `mypy .`; `ruff format --check .`;
`ruff check .`; `manage.py check`; `manage.py makemigrations --check --dry-run`;
`npm run check`; `npm run build`, `build:react`, `build:wip`, `build:showcase`;
`npx playwright test --workers=1`. Browser environment enables `FM1_CAPTURE=1`,
`LOCAL_AUTH_ORIGIN`/`FM1_ORIGIN`/`FM3_ORIGIN` at the isolated legacy server 8014,
`FM4_AUTH_ORIGIN` at flag-on server 8015 and the guarded
`LOCAL_AUTH_RESET_THROTTLE=1`. Capture outputs are directed into the FM4 directory.

Final complete suites supersede earlier failing attempts documented in the WIP
history. FM4-01–03 and FM4-R01–R06 are complete. Remaining differences are approved
temporary branding/font and explicit production-control adaptations in the manifest.
No FM4 blocker remains. FM5's dependency gate is cleared, but FM5 has not begun.
No production rollout is performed; all default flags remain false/absent.
