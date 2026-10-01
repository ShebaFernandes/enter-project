# Authorization Contract

## FM4 typed handoff authority

Comparison selection is a separate target kind. Create/read/replace rechecks source
search ownership, opening/team scope, current eligible candidate IDs, source snapshot
membership and comparison field scope. Max ten unique IDs; preserve request order.
Denied/hidden selection fails closed; it never grants authority to final comparison.
Return generation is authenticated, CSRF-protected, bounded by selection expiry and
accepts no client URL. No selection operation writes recruiting workflow records.

Create/restore/revise/revoke is limited to active Recruiter/Hiring Manager membership
in the exact active tenant and the current bound authenticated SessionCredential.
Every restore additionally checks actor, session-key hash, target kind, purpose,
source ownership/version/existence, expiry and active state. Opening context reuses
current opening/hiring-team authorization. Revoked credentials or lost membership
cannot restore. Wrong tenant/actor/session/type or expired/completed state is
concealed as 404 (existing authentication/membership denials may precede it).

Unsafe operations require CSRF; revisions/revocation require current If-Match.
Results restore is metadata-only. Separate result display rechecks current candidate
eligibility/consent through the existing authorized projection. No handoff grants
candidate access. Recent-search GET remains a separate actor-owned six-item display
projection, not workflow transport. No anonymous access or SECURITY DEFINER.

Authorization is evaluated server-side for every request and background operation. “Conditional” means an explicit tenant membership, object assignment, candidate visibility/consent grant, or approved emergency-access grant is also required. UI visibility is never the control.

| Operation | Candidate | Recruiter | Hiring Manager | Tenant Admin | Platform Security Admin |
|---|---:|---:|---:|---:|---:|
| Read/edit own global profile, consent, visibility | Own | No | No | No | Emergency only |
| Use rights center; download own export; request deletion | Own after verification/step-up as required | No | No | No | Emergency support scope only |
| Upload/read own clean resume | Own | Conditional read | Conditional read | No automatic access | Emergency only |
| Search discoverable candidates | No | Conditional | Conditional | No automatic access | No routine access |
| Read candidate contact/compensation | Own | Conditional + purpose/field scope | Conditional + purpose/field scope | No automatic access | Emergency only |
| Read employment history/informational findings | Own | Conditional + purpose/object/field scope | Conditional + exact shared context and field scope | No automatic access | Emergency only |
| Provision or alter tenant boundary | No | No | No | No | Audited platform-onboarding function only |
| Create/manage business unit or opening | No | Conditional | Conditional | Tenant administration policy | No |
| Create/read recruiter-entered synthetic candidate | No | Conditional in own tenant | Conditional read if shared | Metadata only | No |
| Submit/withdraw own application | Own | No | No | No | No |
| Read tenant application | Own candidate-facing view | Conditional | Conditional | Metadata only unless separately granted | Emergency only |
| Write internal status | No | Conditional | Conditional | No automatic access | No |
| Confirm candidate-facing status/notification | No | Conditional | Conditional | No automatic access | No |
| Read/write candidate-work or application note | No | Conditional to exact context | Conditional to exact shared context; private recruiter notes denied unless separately granted | No automatic access | Emergency only |
| Shortlist/compare/export | No | Conditional | Conditional | No automatic content access | No routine access |
| Preview/confirm candidate contact or share disclosure | No | Conditional + current purpose/field consent | Conditional + current purpose/field consent | No automatic content access | No routine access |
| Manage memberships/tenant settings | No | No | No | Conditional | No |
| View tenant audit metadata | Own rights events | Limited own activity | Limited team activity | Conditional, redacted content | Security scope only |
| Create/complete access review | No | No | No | Conditional within tenant scope | Platform security scope only |
| Request emergency candidate access | No | No | No | No | Yes; cannot self-approve |
| Approve emergency access | No | No | No | No | Different designated Platform Security Admin only |
| Revoke active emergency access | No | No | No | Affected tenant only; no content access conferred | Authorized Platform Security Admin |
| Override abuse block | No | No | No | Tenant-scoped if policy permits | Security-scoped; reason required |

## Enforcement Contract

Every authorization decision evaluates:

1. authenticated identity and current session assurance;
2. one fixed effective role;
3. active tenant context and membership when tenant data is involved;
4. object assignment/team scope;
5. candidate visibility and purpose-specific consent;
6. requested field class and operation;
7. current object state, grant validity, and record version;
8. rate/abuse decision; and
9. emergency grant scope, approval, expiry, and re-authentication when applicable.

Informational findings inherit the source employment record's visibility, consent, purpose, tenant,
object, and field scope. Possession of a finding ID or search-result snapshot never grants access to
the finding or its evidence. `SHORT_TENURE` is not an authorization, eligibility, ranking, status, or
hiring-outcome input.

For `MATCHING_ROLES`, only an `OPENING` search whose authoritative `criteria.context` contains exactly one tenant-owned active `opening_id` may retrieve the profile, and deterministic candidate-controlled preferences are authorization predicates evaluated before ranking. An `AD_HOC` `criteria.context` must contain no `opening_id`, may retrieve only `APPROVED_RECRUITERS` profiles with a non-empty audience explicitly authorizing the tenant, and never bypasses candidate preferences. Saved-search input and output contain no independent opening field. For `APPLIED_ROLES_ONLY`, an application submitted by the candidate and current hiring-team authorization are required. AI output never grants visibility.

Deletion authorization additionally requires recent subject-bound step-up verification and explicit consequence confirmation. Emergency access requests require a non-empty exact `field_scope`; schema acceptance never replaces service-layer authorization and current-state validation.

Tenant provisioning and boundary changes are not tenant administration: they are platform-onboarding actions with separate authorization and audit. Business units remain inside one tenant boundary.

Unknown or unavailable inputs deny access. Allowed and denied sensitive operations emit audit events. Candidate existence, tenant membership, grant status, and rate-limit state are not revealed in public error text.
## Approved frontend entry and read-only additions

| Operation | Public | Candidate | Recruiter / Hiring Manager | Tenant Admin / Platform Security Admin |
|---|---|---|---|---|
| Platform chooser / published opening list | Allowed public essentials only | Same public projection | Same public projection | Same public projection; no additional content |
| List/restore recent search criteria | Denied | Denied | Current active membership, effective search role, exact actor and tenant; active context revalidated | No automatic search access |

Public directory filtering uses the existing public-opening eligibility (OPEN) and returns only id, title, location, work_mode and employment_type. It never queries or returns candidates, team assignments or tenant-private metadata. Validate opaque cursor and bound page size; no client-selected tenant context can expose private roles. Protected recents use server-derived actor/tenant and RLS, current ownership/membership, expiry and AD_HOC context. Wrong-owner/cross-tenant/expired IDs return non-enumerating unavailable responses. Named saved OPENING searches remain separately authorized against the active opening. History contains no result snapshots; executing restored criteria repeats all current eligibility and field checks. Audit sensitive allowed/denied reads through existing minimized audit infrastructure without prompt/criteria bodies. All chooser links preserve existing OIDC/CSRF/session behavior; frontend flags never grant access.
# FM3 public-opening security clarification (2026-10-01)

Anonymous directory/detail/role reads use only active, published, unexpired
PublicOpeningProjection rows and independent public UUIDs. The non-login,
non-owner, NOBYPASSRLS public-reader role has SELECT only on that table and no
source-opening/private-link privileges. No anonymous mutation is allowed.
Source opening forced tenant RLS and its policies are unchanged. Publication
requires current active membership and existing `opening.write` tenant/object
scope, with minimized publication/withdrawal audit events. The projection never
authorizes recruiter or internal management access. Only the authenticated
application workflow resolves a live public UUID through an exactly scoped
private link, then applies the existing source/consent/resume/application checks.
No Tenant Admin or Platform Security Admin candidate-content access is added.

Independent-publication remediation: all three management operations, including
preview GET, require current `opening.write`. Recruiter and Tenant Admin require
active tenant membership and opening/business-unit scope; Hiring Manager, Candidate,
Platform Security Admin and anonymous callers gain no permission. Revalidate before
idempotent replay. Publish requires OPEN, active business unit, non-expired projection,
current ETag and preview digest; withdrawal requires ETag and confirmation but never
closes/pauses the opening. No candidate access is conferred. Management is no-store.
