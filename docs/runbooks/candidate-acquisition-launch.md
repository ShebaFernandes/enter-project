# Candidate acquisition launch

## Release decision

The candidate acquisition flow is ready for a production-topology **staging** release with
synthetic data. It is not approved to collect real resumes until the production tasks T164-T199
in `specs/001-recruiter-candidate-workflows/tasks.md` are complete and signed off.

Use branch `frontend-react-tailwind-parity` as the release source. Do not deploy `main` for this
release.

## Candidate journey in this release

1. A recruiter publishes an opening.
2. The public role URL exposes role metadata and a LinkedIn share action.
3. A candidate follows the link and signs in; the application return URL is preserved.
4. The candidate creates a profile and uploads a resume.
5. The resume must be scanned clean and reach `READY` before application consent can be created.
6. The candidate explicitly confirms role-scoped consent and submits once.
7. The candidate can track the application and exercise privacy rights.

The application endpoint remains the authority for duplicate prevention, resume readiness,
consent, ownership, and role availability. Browser state is not trusted for these decisions.

## Same-day staging path

1. Protect the branch and run the release checks:

   ```bash
   make check
   make test
   make test-contract
   make test-security
   make test-browser
   ```

2. Provision an India-region staging environment with the same topology intended for production:
   private PostgreSQL, private Valkey, quarantine and clean S3 buckets, the resume scanner,
   Django web and worker services behind TLS, Cognito, SES sandbox, and centralized logs.
3. Keep the environment synthetic-only. Disable public indexing and add a prominent staging
   banner. Do not invite candidates or upload real resumes.
4. Store all secrets in the cloud secret manager. Configure, at minimum:
   `APP_ENV`, `DJANGO_SECRET_KEY`, `CANONICAL_ORIGIN`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`,
   `DATABASE_REQUIRE_TLS`, `VALKEY_URL`, `AWS_REGION`, `RESUME_QUARANTINE_BUCKET`,
   `COGNITO_ISSUER`, `COGNITO_DOMAIN`, `COGNITO_CLIENT_ID`, `COGNITO_CLIENT_SECRET`,
   `COGNITO_CALLBACK_URL`, `EMAIL_LOOKUP_KEY`, `FIELD_ENCRYPTION_KEYS`, and
   `AUDIT_CHECKPOINT_REQUIRED`.
5. Build the frontend bundles and application image, run migrations as a one-off release task,
   then start the web and worker services.
6. Require `/health/` to pass at the load balancer before routing staging traffic.
7. Create a synthetic opening and run the complete LinkedIn-link-to-application journey in the
   deployed environment. Verify scan failure, duplicate application, consent rejection, and
   cross-tenant denial paths as well as the happy path.

## Production prerequisites

Production needs all of the following before the manager shares a role publicly:

- Account, domain, DNS, TLS certificate, India region, budget, and named infrastructure owner.
- Network, WAF, load balancer, ECS/Fargate, private endpoints, CloudFront static-only policy,
  encrypted RDS/Valkey/S3, Cognito, SES, monitoring, audit storage, and recovery automation.
- Capacity, resilience, concurrency, retention, accessibility, browser performance, security,
  DAST, threat-model, model-promotion, and independent penetration-test evidence.
- Incident response, access review, migration/rollback, rollout controls, candidate and recruiter
  usability evidence, India legal/privacy approval, backup restore, deletion replay, and regional
  recovery evidence.
- A completed production-readiness record with commands, versions, outcomes, waivers, and named
  approvers.

Keep `WHATSAPP_ENABLED=false` until a provider and the legal/privacy approval explicitly cover
the channel. Email must remain in SES sandbox until sender identity, suppression handling, and
production access are approved.

## Go/no-go rule

The staging URL may be shared only with the internal test group and only for synthetic data.
The public LinkedIn post is a **no-go** until every real-data prerequisite above has evidence and
an accountable owner has approved the release. A successful build or deployment alone is not a
real-data launch approval.
