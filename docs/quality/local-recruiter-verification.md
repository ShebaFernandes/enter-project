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
