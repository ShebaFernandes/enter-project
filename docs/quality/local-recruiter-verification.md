# Local authenticated recruiter verification

This workflow creates a short-lived synthetic recruiter session for local verification. It does not bypass application authorization: the resulting browser session has a normal `SessionCredential` with `WORKFORCE_MFA`, an active recruiter membership in one synthetic tenant, and the normal tenant, purpose, consent, visibility, field-scope, RLS, and CSRF checks.

## Safety boundary

- The route is registered only when `LOCAL_SYNTHETIC_AUTH_ENABLED` is true in local/test settings.
- The handler independently rejects any environment other than `local` or `test`.
- Production settings inherit `LOCAL_SYNTHETIC_AUTH_ENABLED = False`; therefore the route is absent and the runtime guard also fails closed.
- The command creates only deterministic `*.invalid` synthetic identities and synthetic candidate/employment data.
- The bearer token is random, stored only as a SHA-256-derived cache key, expires after ten minutes, and is deleted on first use.
- Token exchange calls the normal sign-in service and creates the same assured session record used by workforce authentication. It does not create grants or bypass authorization.

## Manual verification

1. Start or rebuild the local environment:

   ```sh
   docker compose up -d --build
   npm --prefix app run build
   ```

2. Create a one-time URL:

   ```sh
   docker compose exec web python manage.py bootstrap_local_recruiter
   ```

3. Open the printed URL within ten minutes. It redirects to the synthetic tenant's recruiter search page.
4. Keep `Ad-hoc search`, enter `Python` in the first criterion, and run the search.
5. Verify that `Synthetic Search Candidate` appears with the neutral eight-month `SHORT_TENURE` message and supporting evidence.
6. Open `View authorized details` and confirm the same permitted finding evidence appears.
7. Select `Sign out`, then use browser Back. The recruiter workspace must not reappear and the synthetic bootstrap URL cannot be reused.

## Automated authenticated browser verification

Generate JSON output, copy its `url` value into the environment variable, and run the browser test against the local Django service:

```sh
docker compose exec web python manage.py bootstrap_local_recruiter --json
LOCAL_RECRUITER_BOOTSTRAP_URL='PASTE_THE_PRINTED_URL' npm --prefix app run test:browser
```

The authenticated test is skipped when the environment variable is absent, so ordinary browser tests never create an authentication shortcut. The Django integration test independently verifies one-time use, MFA assurance, search, candidate detail, finding authorization, sign-out, and the production runtime guard.

## Post-FM6: organization records versus discoverable profiles

Diagnosis: **expected organization-record separation plus a local fixture category mismatch**,
not an FM6 rendering, handoff or authorization defect.

Organization Create synthetic candidate writes `RecruiterEnteredCandidate` with immutable
`RECRUITER_ENTERED_SYNTHETIC` provenance and tenant RLS. It does not create a candidate identity,
`CandidateProfile`, `CandidateSkill`, consent or visibility rule, and cannot impersonate a
candidate's consent. Search reads authorized published CandidateProfile records; it does not
union organization records or wait for an asynchronous indexing job. Existing database lookup
indexes do not turn organization records into profiles. The data-model's general “search
eligibility” wording is not permission to synthesize consent or merge these separate records.

The existing `bootstrap_local_recruiter` command already supplies a complete profile:

| Gate | Synthetic fixture |
| --- | --- |
| Session / tenant | One-time local-only token, active recruiter membership in `local-synthetic-recruiting` |
| Profile | Published Synthetic Search Candidate, Bengaluru, 5 years, Python skill |
| Category | `engineer` and `software engineer`; category matching uses exact case-insensitive membership, not substring matching |
| Consent | Current RECRUITING_DISCOVERY consent, profile/skills/employment_history fields, approved synthetic tenant |
| Visibility | APPROVED_RECRUITERS with the same approved tenant |
| Search context | **Ad-hoc search**; an opening search instead requires MATCHING_ROLES and matching role/location/arrangement preferences |
| Findings | Confirmed synthetic eight-month employment; SHORT_TENURE remains informational |

Previously the fixture contained only `software engineer`, while the requested prompt produces
the deterministic category `engineer`. All four REQUIREMENT/ALL criteria therefore returned zero
results despite valid discovery consent. Only the local seed categories were corrected. Rerun
the command to refresh that fixed synthetic fixture, then execute a **new** search (old result
snapshots are not retroactively populated). No matching algorithm, consent, RLS or API changed.

### Exact local React reproduction

Use the same local database and cache configuration in both terminals. With dependencies and
current Vite assets installed, from the repository:

```sh
cd app
```

Start a separate local verification server; process-only flags avoid editing committed settings:

```sh
DJANGO_SETTINGS_MODULE=config.settings.local .venv/bin/python -c 'import django; django.setup(); from django.conf import settings; settings.FRONTEND_REACT_ROUTES={"recruiter-search-page":True,"recruiter-results-page":True}; from django.core.management import execute_from_command_line; execute_from_command_line(["manage.py","runserver","127.0.0.1:8018","--noreload","--nostatic"])'
```

In another terminal, also from `app`, seed and obtain a fresh one-time login URL:

```sh
DJANGO_SETTINGS_MODULE=config.settings.local .venv/bin/python manage.py bootstrap_local_recruiter --base-url http://127.0.0.1:8018
```

Open the printed URL within ten minutes. Keep **Ad-hoc search**. Enter:
`Python engineer in Bengaluru with at least 5 years experience`. Click Search and open
Synthetic Search Candidate's authorized details. Confirm the four applied criteria and the
informational employment finding. Inspect browser storage: localStorage/sessionStorage remain
empty. Never paste the one-time token into committed evidence. If using an existing server on
8000, use that origin instead and restart it to load the corrected seed code.

This verification used the pre-existing working-tree deterministic AI fallback (left unchanged),
not a newly installed model stub. A checkout that reports unvalidated/unavailable interpretation
must still show inline clarification; this fixture correction does not authorize bypassing it.

### Verification recorded

The new PostgreSQL regression reproduced zero results before the one-line fixture correction,
then verified the complete query, organization/profile separation, authorized detail and the
opening-context distinction. Focused discovery/RLS/finding/session tests: **19 passed**.
Authenticated Playwright: **2 passed** (`local-discovery.spec.ts` and the existing FM6 journey),
using fresh one-time URLs, real APIs and isolated synthetic PostgreSQL/cache state. Visually
inspected the live [result/detail screenshot](../evidence/frontend-migration/fm6/local-discovery-detail.png):
one authorized result, four applied criteria, Bengaluru, Python, 5.00 years and permitted detail.
No external screen-reader/manual-device testing is claimed by this focused check.

Run the focused browser tests with a local server and fresh bootstrap generated by the helper:

```sh
DJANGO_SETTINGS_MODULE=config.settings.local FM6_AUTH_ORIGIN=http://127.0.0.1:8018 npx playwright test recruiter/local-discovery.spec.ts recruiter/fm6-authenticated.spec.ts --workers=1
```

No FM7 work or product requirement changes. Existing local flags and AI-fallback edits were
preserved. FM7 remains cleared by the completed FM6 gate.
