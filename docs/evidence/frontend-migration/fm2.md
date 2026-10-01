# FM2 — shared React/Tailwind foundation

Scope: FM2-01 → FM2-02 → FM2-03 only, 2026-10-01. FM1-01–03 remain complete. The FM1–FM14 umbrella checklist remains unchecked with explicit user approval to proceed. No FM3 route, production React registration, API, model, migration, authorization or workflow change.

## Acceptance and implementation

FM2-01 defined failing-first manifest/escaped-bootstrap tests and component/browser acceptance. The first test run failed with the expected missing `frontend_assets` module. Subsequent focused tests caught a formatter-split Django tag, CSP-disallowed inline CSS in the test harness, and stretched card spacing; all were corrected before the full regression run. CSP was not relaxed.

FM2-02 delivers these reusable boundaries:

| Files | Responsibility |
|---|---|
| `app/frontend/react/components.tsx` | AppShell, Header/Wordmark, named WorkspaceNavigation, Container, ResponsiveGrid, Button/IconButton, TextInput/Textarea/Select, Checkbox/Radio, associated Field/help/error, Card, Chip/Badge, Alert/StatusMessage, Loading/skeleton, EmptyState, ErrorState, DegradedState, Dialog, ConflictPanel, Table/List, VisuallyHidden/SkipLink |
| `app/frontend/react/foundation.css` | Prefixed Tailwind theme; shared semantic classes scoped to `.enter-ui`; no preflight; responsive and reduced-motion behavior |
| `app/frontend/react/mount.tsx`, `entry.ts` | Validated PageBootstrap, exclusive root ownership, session check, error boundary, abort/unmount cleanup and foundation exports; no automatic feature mount |
| `app/frontend/shared/api-client.ts`, `tenant-client.ts` | Shared same-origin transport; existing tenant client delegates without changing server authority |
| `app/frontend/templates/react/page.html`, `base.html` | Escaped JSON bootstrap, Django CSRF input, empty React root, safe no-JavaScript/bundle-failure recovery; mutually exclusive full-page ownership |
| `app/modules/operations/frontend_assets.py`, `frontend.py` | Local manifest/file validation and fail-to-legacy behavior for missing/invalid assets, still behind the existing empty verified-route registry |
| `app/vite.config.ts`, `package.json` | Independent legacy, retained checkpoint WIP, React foundation and test-only showcase builds; no dependency upgrades |
| `app/tests/unit/test_frontend_foundation.py` | Manifest missing/path traversal/external path rejection, escaped bootstrap, fail-to-legacy rollout integration |
| `app/tests/browser/fm2-foundation.spec.ts`, `fixtures/fm2.html`, `fixtures/fm2-showcase.tsx` | Seven component/transport/mount/accessibility tests and deterministic showcase; test-only example strings, no mock production candidates |
| `app/tests/browser/fm1-baselines.spec.ts` | Optional output directory permits regression recapture without replacing FM1 reference evidence; existing assertions preserved |

### Tokens and visual source

Source: immutable mockup `:root`, chrome, field, card and dialog rules, plus approved `frontend-migration.md`. FM1 reference screenshots were inspected alongside foundation captures. This is component-language parity, not a claim that the test showcase reproduces a product screen.

- Paper `#F4F5EF`, raised `#FFFFFF`, ink `#111342`, muted `#4B5563`, faint `#818B98`, hairline `#D7DBD2`.
- Gold `#A76F15/#F6E7C6`, sage `#276955/#DDEDE6`, clay `#A13E2D/#F3DDD8`, unknown `#6F756C`. Labels never rely on color alone. Small gold/unknown text uses contrast-safe semantic variants `#80520D`/`#565B54`; faint is not used for essential small text.
- System/local sans, Georgia-compatible display, system monospace; replaceable `font-sans`, `font-display`, `font-mono`. Lowercase text wordmark **enter**. No remote font request, invented logo or redrawn asset.
- Four-pixel base spacing plus named 6/10/14/18/22/26px steps; 1px border, 6/8px radii and pill chips; exact restrained reference shadows.
- Search/profile/public widths 1360/1180/1080px, fluid gutters; 860px stack breakpoint. Table retains native semantics in an independently scrollable named region when needed; no page overflow at 320px.
- Explicit hover/active/disabled/selected/error states, 44px controls, visible 3px sage focus, reduced-motion override. Control boundaries are darker than reference hairlines to preserve non-text contrast. Nonessential decorative card borders retain the source hairline.

Intentional differences: system font metrics instead of unavailable Inter/Fraunces/Roboto Mono; text wordmark instead of missing approved logo; larger accessible controls/focus and contrast-safe small text; a component gallery rather than a migrated page. Missing branding assets are not an FM3 blocker. Foundation token/component boundaries allow later replacement without restructuring pages.

### Mount, transport and recovery

Django remains the URL/session/CSRF/authentication/authorization boundary. Bootstrap comes from `json_script`, never executable inline JavaScript. The factory accepts only a code-owned page registry; URLs, cookies and browser storage cannot register pages. A root must be empty, outside any existing main, on a server-selected React page, and not owned by another renderer. It reserves ownership before asynchronous startup. The foundation entry exports primitives but registers **zero** pages.

Protected page startup checks existing `GET /api/v1/session`; every feature API must still enforce its own current object/field/consent authorization. React does not read cookies. The API client uses browser-managed same-origin credentials, the Django hidden CSRF input, consistent tenant header, no-store and no cross-origin redirects. ETags and caller-supplied idempotency keys are preserved; no mutation retries, automatic merges or authorization policy are implemented. ConflictPanel accepts the existing ConflictPayload type and delegates explicit discard/review/resubmit actions to later page controllers; it does not write or infer data. API problem bodies are not automatically rendered or logged.

Page state is React memory only. Navigation/unmount aborts pending transport and clears the root. BFCache restoration reloads to re-request current authorized state. Sign-out/tenant-switch integrations in later slices must dispose the current page and use existing server transitions; no state-store migration is implied. A component crash clears React content and focuses safe recovery text. Bundle failure leaves static recovery content. Neither path replays a mutation or silently swaps renderers.

Manifest resolution is opt-in for future reviewed registry entries with `manifest: "react"`. It rejects missing files, traversal, absolute/external paths and escaping symlinks. Missing/invalid manifests leave the route on legacy. `FRONTEND_REACT_ROUTES` and `VERIFIED_REACT_ROUTES` remain `{}`. Immediate rollback remains removal/false of the server flag at the same URL, with no data changes. The base template gives React an exclusive full-page root instead of nesting AppShell's main under legacy main.

### CSS and build isolation

Foundation follows Tailwind's documented [preflight opt-out](https://tailwindcss.com/docs/preflight) by importing theme/utilities individually, with the `fm` prefix and automatic scanning disabled. Tailwind is applied through semantic shared component selectors, not arbitrary per-page styles. All visual element selectors are `.enter-ui`-scoped; namespaced theme variables do not reset native legacy elements. Tests load foundation CSS beside unscoped legacy controls and verify unchanged computed styles. Existing legacy/WIP isolation and rollout tests also pass.

Build order matters: `npm run build` cleans `static/dist`; then `build:wip`, `build:react`, and test-only `build:showcase` recreate their own independent directories/manifests. Production packages should omit `static/dist/showcase` and the test fixtures; no Django route or production template references them. Retained WIP remains unapproved and unchanged.

## Visual and accessibility evidence

Committed goldens: `app/tests/browser/fm2-foundation.spec.ts-snapshots/` — 15 PNGs: `foundation-*`, `dialog-*`, `reconciliation-*`, each at 1440×1000, 1024×768, 390×844, 320×844 and 1440×1000 with CSS zoom 200%. Full-page heights expand with content. Screenshot assertions ran again without `--update-snapshots` in the complete suite and passed. FM1 screenshots and immutable mockup are unchanged.

Automated: zero serious/critical axe findings across every captured gallery, dialog and validation/conflict state; no page overflow; associated help/error, explicit live status, disabled controls, dialog opening/trap/Escape/focus return, reduced motion, missing bundle/session, malformed bootstrap, duplicate ownership, tenant/origin denial, CSRF, ETag/idempotency, and state cleanup covered.

Manual Chrome/macOS keyboard and screen-reader-oriented accessibility-tree review:

| Check | Observed result |
|---|---|
| Skip and main | First Tab exposes visible skip link; Enter targets main; next Tab reaches the primary action |
| Names/headings | One active main, H1 then H2 sections, named workspace navigation, visible labels and choice states in native tree |
| Keyboard/focus | Disabled button skipped; visible outline; keyboard activation updates live status |
| Dialog | Named Review changes dialog; Close initially focused; Shift+Tab wraps to Keep editing; Escape returns to Open dialog |
| Validation | Empty example submission exposes associated validation text and updated status; no data sent |
| Conflict | Focus moves to labeled reconciliation region; stored/attempted synthetic values and three explicit actions exposed |
| Responsive review | Desktop and narrow captures visually inspected; controls wrap, dialog remains usable; table state words remain intact after correction |

Scope of manual signoff: native accessibility-tree/keyboard review, not VoiceOver/NVDA speech-output certification. 200% captures use CSS zoom as the automated reflow approximation; this is not an additional claim of native browser-zoom or production-wide assistive-technology certification. Later page migrations retain their own manual acceptance requirements.

## Verification results

Environment: Node 24.21.0, Python 3.14.7, repository-locked React 19.1.1, Tailwind 4.1.14, Vite 7.3.6 and Playwright 1.55.1. Existing local PostgreSQL/Valkey services and real one-time synthetic session bootstrap were reused.

| Check | Result |
|---|---|
| Legacy / retained WIP / React / test-showcase builds | PASS: 27 / 27 / 29 / 30 modules respectively |
| TypeScript / ESLint / Prettier | PASS |
| New Python foundation + existing rollout focused tests | 8 passed (3 new, 5 existing) |
| Complete PostgreSQL suite, run once after implementation | **278 passed, 1 expected audit-trigger fixture skip; 279 collected** |
| Repository-wide `mypy .` | PASS, **217 files**, original scope unchanged |
| Ruff lint / format | PASS, 217 files |
| Django system / migration drift / applied migration checks | PASS; no schema changes |
| Complete non-authenticated browser suite | **42 passed**, including all 7 FM2 tests and previous 35 tests |
| Existing authenticated scenarios | **5 passed**: recruiter search, comparison, candidate application/status, governance, organization |
| Existing FM1 capture regression | **1 passed**, 130 recaptures in separate ignored output; committed FM1 reference evidence unchanged |
| Browser collection | 48 tests across 18 files; no prior tests removed |
| Mockup SHA-256, both copies | `daeb180c0a2ec55994422e050b14edca9f62c431dea9cb113f4c33378867b9e9`, unchanged |
| Production rollout | Default-off and empty verified registry; legacy remains production default |

Reproduce from `app/`: build in the order above; run `.venv/bin/pytest` with existing PostgreSQL/Valkey local environment, `.venv/bin/mypy .`, Ruff, Django checks, `npm run check`, and `npx playwright test --grep-invert authenticated --workers=2`. Issue fresh one-time bootstrap URLs for each existing authenticated spec. Run optional FM1 recapture with `FM1_CAPTURE=1 FM1_ORIGIN=http://127.0.0.1:8002 FM1_OUTPUT=test-results/fm1-fm2-verification` to preserve the committed FM1 evidence. The isolated showcase can be served by the existing Playwright test server at `/app/tests/browser/fixtures/fm2.html`; it is not a Django production route.

Final disposition: **FM2-01, FM2-02 and FM2-03 complete.** All 48 browser tests passed in the regression batches, including the opt-in baseline capture. FM3's dependency gate is cleared; FM3 has not begun. No production route was cut over or enabled. The FM1–FM14 umbrella acceptance item remains unchecked. No remaining FM2 blocker; font/logo fallbacks and later page-specific acceptance remain explicit.
