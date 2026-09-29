# Authorization Contract

Authorization is evaluated server-side for every request and background operation. “Conditional” means an explicit tenant membership, object assignment, candidate visibility/consent grant, or approved emergency-access grant is also required. UI visibility is never the control.

| Operation | Candidate | Recruiter | Hiring Manager | Tenant Admin | Platform Security Admin |
|---|---:|---:|---:|---:|---:|
| Read/edit own global profile, consent, visibility | Own | No | No | No | Emergency only |
| Use rights center; download own export; request deletion | Own after verification/step-up as required | No | No | No | Emergency support scope only |
| Upload/read own clean resume | Own | Conditional read | Conditional read | No automatic access | Emergency only |
| Search discoverable candidates | No | Conditional | Conditional | No automatic access | No routine access |
| Read candidate contact/compensation | Own | Conditional + purpose/field scope | Conditional + purpose/field scope | No automatic access | Emergency only |
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

For `MATCHING_ROLES`, only an `OPENING` search whose authoritative `criteria.context` contains exactly one tenant-owned active `opening_id` may retrieve the profile, and deterministic candidate-controlled preferences are authorization predicates evaluated before ranking. An `AD_HOC` `criteria.context` must contain no `opening_id`, may retrieve only `APPROVED_RECRUITERS` profiles with a non-empty audience explicitly authorizing the tenant, and never bypasses candidate preferences. Saved-search input and output contain no independent opening field. For `APPLIED_ROLES_ONLY`, an application submitted by the candidate and current hiring-team authorization are required. AI output never grants visibility.

Deletion authorization additionally requires recent subject-bound step-up verification and explicit consequence confirmation. Emergency access requests require a non-empty exact `field_scope`; schema acceptance never replaces service-layer authorization and current-state validation.

Tenant provisioning and boundary changes are not tenant administration: they are platform-onboarding actions with separate authorization and audit. Business units remain inside one tenant boundary.

Unknown or unavailable inputs deny access. Allowed and denied sensitive operations emit audit events. Candidate existence, tenant membership, grant status, and rate-limit state are not revealed in public error text.
