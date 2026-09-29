# Feature Specification: Integrated Recruiter and Candidate Workflows

**Feature Branch**: `none`

**Created**: 2026-09-28

**Status**: Approved

**Approved**: 2026-09-29

**Input**: User description: "Use enter_recruiter_recruiter_candidate_ux.html as the existing
visual and functional mockup. Create a feature specification describing its recruiter and
candidate workflows, user requirements, interactions, states, validation, accessibility
requirements, and acceptance criteria. Do not implement or modify the HTML yet."

## Clarifications

### Session 2026-09-28

- Q: Should this feature remain a synthetic-data prototype, or must it support real candidate data
  in production? → A: Production-ready system that may accept real candidate data.
- Q: Which candidate-data jurisdictions must the initial production launch support? → A: India
  only for the initial production launch.
- Q: How long should an inactive candidate profile be retained without renewed consent? → A:
  Retain it for 12 months, request renewed consent 30 days before expiry, then delete the
  identifiable profile and resume or retain only irreversibly anonymized analytics if unanswered;
  active hiring processes and documented legal holds are excluded.
- Q: When the same candidate applies to multiple roles using the same verified email, how should
  their records be organized? → A: Maintain one candidate-controlled profile per verified email,
  linked to a separate application for each role; each application retains its own status, answers,
  consent context, timestamps, notes, and audit history.
- Q: How should recruiter workflow statuses update the candidate-facing application status and
  trigger notifications? → A: Suggest a mapped candidate-facing status, but require recruiter
  preview and explicit confirmation before publishing it or sending any notification.
- Q: Which authorization model should govern candidate, recruiter, hiring-team,
  tenant-administration, and platform-administration access at launch? → A: Use five fixed,
  least-privilege roles: Candidate, Recruiter, Hiring Manager, Tenant Admin, and Platform Security
  Admin. Enforce tenant- and object-level authorization on every data operation. Tenant Admins have
  no automatic candidate-content access; Platform Security Admin access is time-limited,
  reason-bound, explicitly approved, and fully audited.
- Q: How should candidate profiles and recruiter-owned records be isolated between company tenants?
  → A: Maintain one candidate-controlled profile governed by candidate visibility and consent;
  strictly isolate each company's openings, applications, searches, statuses, notes, shortlists,
  exports, communications, and audit records. Permit cross-tenant disclosure only with explicit,
  purpose-specific candidate consent and authorization.
- Q: Which production service targets should apply for availability, recovery, backups, and initial
  launch scale? → A: Target 99.9% monthly availability, a 15-minute recovery point, a 4-hour
  recovery time, encrypted backups retained for 35 days with quarterly restore testing, capacity
  for 100 tenants, 1 million candidate profiles, and 1,000 concurrent active users, and a 3-second
  p95 response time for normal searches at expected launch load.
- Q: Which rate-limiting and abuse-protection baseline should apply at launch? → A: Apply balanced,
  tiered limits using verified identity and network signals: 5 failed sign-in attempts per identity
  and network in 15 minutes; 5 verification codes per address and 20 per network per hour; 10 resume
  uploads per verified candidate per hour; 20 applications per candidate per day; 60 searches per
  recruiter per minute; and 5 exports per authorized user per hour. Use escalating temporary
  delays, anomaly-based tightening, no permanent automatic lockout, and complete auditing of blocks
  and authorized overrides.
- Q: How must concurrent edits, critical-service failures, resume-parsing failures, notifications,
  and administrative access be handled? → A: Use optimistic conflict detection with explicit user
  reconciliation; reject stale consent, visibility, status, note, and administration writes and
  show the latest authorized stored state beside the attempted changes. Fail closed for identity,
  authorization, primary-data, and file-security failures. Permit manual profile entry after a
  parsing failure, but never expose a resume before a successful security scan. Queue notifications
  with idempotency keys, no more than five delivery attempts within 24 hours, dead-letter handling,
  and visible pending or failed states. Record every administrative access decision and action in a
  minimized, separately protected audit history.
- Q: How should candidates exercise data access, correction, consent withdrawal, export, and
  deletion rights? → A: Provide a verified self-service rights center. Make access and correction
  immediate; apply consent withdrawal and profile hiding immediately; generate exports within 24
  hours with a 24-hour download expiry; and require step-up verification plus explicit confirmation
  for deletion. Hide the profile immediately and complete deletion within 30 days, except for
  clearly identified active-process or legal-hold records. Show request status and provide support
  escalation.
- Q: Should matching-role visibility allow qualifying recruiter discovery or mean applied roles
  only? → A: Provide four separate visibility settings: Approved recruiters, Matching roles,
  Applied roles only, and Not looking. Matching-role discovery requires an active opening and
  deterministic candidate-controlled preferences; AI scores alone cannot make a candidate
  eligible. Applied-role-only profiles are visible exclusively to authorized hiring teams for
  applications the candidate submitted.
- Q: Which candidate-facing status vocabulary and mapping is authoritative? → A: Use only Applied,
  Profile viewed, Shortlisted, Recruiter interested, Interview requested, Offer made, Not selected,
  and Withdrawn.
  Successful candidate submission publishes Applied. First authorized view may suggest Profile
  viewed; internal Shortlisted may suggest Shortlisted; Contacted or Screening may suggest Recruiter
  interested; Interviewing may suggest Interview requested; Offered may suggest Offer made; and
  Rejected may suggest Not selected. Candidate withdrawal publishes Withdrawn through the verified
  candidate action.
  Every recruiter-originated suggestion requires preview and explicit confirmation. Sourced,
  Not relevant, Hired, and any other internal state have no candidate-facing equivalent and
  leave the published candidate-facing status unchanged.
- Q: Where should notes and workflow status be stored for a sourced candidate who has no
  application? → A: Create a tenant-scoped candidate-work record when an authorized recruiter first
  views, notes, shortlists, or changes the internal status of a sourced candidate. Link it to the
  candidate, originating search, and optional opening, and store internal status, notes, shortlist
  state, reasons, and audit history there. If the candidate later applies, link the application
  without merging or overwriting either record.
- Q: Which launch governance model defines company and tenant boundaries and approves Platform
  Security Admin emergency access? → A: One tenant represents one contracted customer company or
  legally separate recruiting boundary. Only platform onboarding may provision tenants; recruiters
  may create business-unit contexts and openings within their tenant. Break-glass access requires
  approval by a different Platform Security Admin, immediate affected-Tenant-Admin notification,
  automatic expiry, narrow scope, stated justification, revocation capability, and complete audit.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Candidate Creates a Controlled Profile (Priority: P1)

A candidate opens the public candidate platform without an internal recruiter account, uploads a
resume, reviews the information extracted from it, fills only missing essentials, chooses how the
profile may be discovered, gives recruitment consent, and previews or submits the profile.

**Why this priority**: Candidate-supplied, candidate-controlled information is the source of value
for every downstream discovery and recruiting workflow.

**Independent Test**: Start from the signed-out landing experience, enter the candidate platform,
upload a supported synthetic resume, correct the preview, select visibility and work preferences,
consent, and submit. The test delivers a complete candidate profile without recruiter involvement.

**Acceptance Scenarios**:

1. **Given** a signed-out visitor, **When** they choose the candidate platform, **Then** they can
   begin the candidate flow without entering recruiter credentials.
2. **Given** no resume has been selected, **When** the candidate views the form, **Then** the page
   explains what recruiters will see, what the candidate controls, and what follows upload while
   keeping profile-detail fields out of the primary flow.
3. **Given** a supported resume, **When** the candidate uploads it, **Then** the system communicates
   progress, presents extracted values as a reviewable preview, marks their source, and identifies
   required information it could not determine.
4. **Given** extracted values, **When** the candidate edits a value, **Then** the candidate's edit is
   retained and is not silently replaced by a later automated suggestion.
5. **Given** a complete profile and affirmative consent, **When** the candidate submits with a
   recruiter-visible option, **Then** the system confirms the selected visibility and makes the
   profile eligible only for the permitted recruiter audience.
6. **Given** the candidate selects "Not looking right now," **When** they save the preference,
   **Then** the system confirms the preference and excludes the profile from recruiter discovery.
7. **Given** missing or invalid required information, **When** the candidate attempts submission,
   **Then** no profile is published, a summary identifies every problem, and focus moves to the
   first invalid field without discarding valid entries.
8. **Given** a verified candidate, **When** they use the rights center, **Then** they can access and
   correct their data immediately, withdraw consent or hide their profile immediately, request an
   export, request deletion with step-up verification and explicit confirmation, track each request,
   understand any active-process or legal-hold exception, and escalate a failed or disputed request
   to support.
9. **Given** a candidate selects Matching roles, **When** an authorized recruiter searches from an
   active opening, **Then** the profile is eligible only when deterministic candidate-controlled
   role, location, work-arrangement, and other selected preferences match; an AI score alone cannot
   make it eligible.
10. **Given** a candidate selects Applied roles only, **When** any recruiter or hiring manager
    requests the profile, **Then** access is limited to authorized hiring teams for applications the
    candidate submitted and the profile is absent from sourcing searches for other roles.

---

### User Story 2 - Recruiter Searches for Candidates (Priority: P1)

An authorized recruiter describes a hiring need in natural language or selects a suggested search.
The system interprets role, location, experience, skills, evidence signals, preferences, and
exclusions, then returns relevant candidates with understandable reasons.

**Why this priority**: Finding a credible shortlist is the recruiter's primary job and the central
business outcome of the experience.

**Independent Test**: Sign in with an eligible work identity, submit a search containing location,
experience, skills, and preference signals, and verify that results reflect the criteria and show
why each person matched.

**Acceptance Scenarios**:

1. **Given** a signed-out recruiter, **When** they submit a valid verified work email, **Then** they
   enter the recruiter search workspace and their signed-in state is clearly displayed.
2. **Given** an empty, malformed, personal-domain, or unverified recruiter email, **When** sign-in is
   attempted, **Then** access is denied with a specific error associated with the email field.
3. **Given** an authenticated recruiter, **When** they enter a sufficiently clear hiring prompt,
   **Then** the system interprets the criteria and presents ranked results without unnecessary
   confirmation.
4. **Given** an ambiguous or incomplete prompt, **When** search is requested, **Then** the system
   presents its interpretation for review before running the search.
5. **Given** speech input is available and permitted, **When** the recruiter dictates a search,
   **Then** the transcript appears as editable search text and is not submitted until the recruiter
   explicitly searches.
6. **Given** speech input is unavailable, denied, or fails, **When** the recruiter activates it,
   **Then** the system reports the condition and leaves typed search fully usable.
7. **Given** matching profiles, **When** results appear, **Then** they are ordered by relevance,
   limited to the requested result count, and each includes evidence supporting the match.
8. **Given** no matching profiles, **When** the search completes, **Then** the system shows a clear
   no-results state and suggests broadening criteria or changing filters.
9. **Given** an ad-hoc search, **When** it executes, **Then** it can retrieve only profiles whose
   `APPROVED_RECRUITERS` audience explicitly authorizes the tenant and it never bypasses candidate
   preferences.
10. **Given** a search intended to discover `MATCHING_ROLES` profiles, **When** it executes, **Then**
    its context is `OPENING`, it references an active opening, and deterministic candidate
    preferences are satisfied before any ranking occurs.

---

### User Story 3 - Recruiter Reviews Search Intent (Priority: P1)

A recruiter reviews how a search was interpreted, sees the expected impact of strictness choices,
and adds, edits, or removes criteria before committing to a search.

**Why this priority**: Reviewable criteria reduce hidden assumptions and let recruiters correct a
search before candidates are included or excluded.

**Independent Test**: Use an incomplete or ambiguous prompt, modify every supported criterion type,
switch between matching any and all alternatives, and run the revised search. Results must reflect
the final visible criteria.

**Acceptance Scenarios**:

1. **Given** interpreted criteria, **When** the review opens, **Then** the original prompt, result
   limit, estimated in-scope count, all detected criteria, and their strict or preferential role
   are visible.
2. **Given** a criterion, **When** the recruiter edits or removes it, **Then** the visible
   interpretation and expected candidate count update before search execution.
3. **Given** a new requirement, preference, or exclusion, **When** the recruiter adds it, **Then**
   it references an explicit criteria group with a stable ID and affects the next search.
4. **Given** a criteria group, **When** the recruiter switches its operator between `ANY` and `ALL`,
   **Then** the stable group ID is preserved, the interface explains the difference, and the
   estimated result impact updates.
5. **Given** the reviewed criteria, **When** the recruiter runs the search, **Then** the results are
   based on exactly the criteria shown at confirmation time.

---

### User Story 4 - Recruiter Evaluates and Manages Candidates (Priority: P2)

A recruiter scans result cards, filters the list, inspects a candidate's profile and evidence,
records private notes, changes recruiting status, captures rejection feedback, and contacts or
shares the candidate through permitted actions.

**Why this priority**: Search results become useful only when recruiters can evaluate evidence and
advance or close candidates while preserving context.

**Independent Test**: From a populated result set, filter by status, open a profile, navigate its
sections, save a note, change status, record "not relevant" feedback, and initiate one permitted
contact action.

**Acceptance Scenarios**:

1. **Given** a result set, **When** the recruiter scans a candidate card, **Then** they can identify
   role, company, location, experience, notice period, compensation availability, freshness,
   skills, stage signals, current status, and key match evidence without opening the profile.
2. **Given** a selected candidate, **When** the recruiter opens the profile, **Then** the candidate
   is marked viewed and overview, private notes, permitted contact details, actions, resume,
   evidence provenance, unknowns, and match limitations are available in a modal or detail view.
3. **Given** a private note, **When** the recruiter saves it, **Then** confirmation appears and the
   note remains associated with that candidate but is never shown in the candidate experience.
4. **Given** a status change, **When** it is saved, **Then** the new status appears consistently on
   the card and profile and is scoped to the relevant search or opening where appropriate.
5. **Given** "Not relevant" is selected, **When** the recruiter confirms reasons and an optional
   note, **Then** the feedback is saved for search-quality review; cancelling returns the candidate
   to the prior non-terminal state.
6. **Given** a permitted contact or sharing action, **When** the recruiter activates it, **Then** the
   destination and minimum disclosed data are clear before information leaves the platform.
7. **Given** an internal recruiter status change, **When** a candidate-facing status is suggested,
   **Then** the recruiter can preview its wording, audience, and notification channels, and no
   candidate-visible change occurs until the recruiter explicitly confirms it.
8. **Given** a sourced candidate with no application, **When** an authorized recruiter first views,
   notes, shortlists, or changes the candidate's internal status, **Then** the action is stored in a
   tenant-scoped candidate-work record linked to the candidate, originating search, and optional
   opening rather than creating an application.
9. **Given** a sourced candidate later submits an application, **When** the records are linked,
   **Then** the candidate-work record and application retain their own status, notes, reasons,
   timestamps, and audit history without merging or overwriting either record.

---

### User Story 5 - Recruiter Compares a Shortlist (Priority: P2)

A recruiter selects candidates from a result set and compares the same decision-relevant facts and
evidence side by side.

**Why this priority**: Structured comparison helps recruiters make consistent decisions without
losing the context of the active search.

**Independent Test**: Select two or more result cards, open comparison, verify consistent fields and
match reasons, close the comparison, and confirm selections and result state remain intact.

**Acceptance Scenarios**:

1. **Given** result cards, **When** the recruiter selects or clears comparison candidates, **Then**
   the comparison count updates and the selection state is preserved during result interactions.
2. **Given** selected candidates, **When** comparison opens, **Then** each candidate is shown with
   the same location, experience, notice, compensation availability, skills, and match-evidence
   categories; unknown values are explicitly labeled rather than inferred.
3. **Given** no selected candidates, **When** comparison opens, **Then** the system explains how to
   select candidates instead of showing an empty or broken comparison.
4. **Given** an open comparison, **When** the recruiter closes it by its close control or permitted
   outside action, **Then** focus returns to the invoking control and the underlying results remain.

---

### User Story 6 - Candidate Applies and Tracks Progress (Priority: P2)

A candidate follows a public role link, reviews open roles and what happens after applying, submits
a quick application without an internal account, and receives understandable progress updates
through chosen channels.

**Why this priority**: A low-friction application and transparent status experience convert public
interest into candidate participation and reduce uncertainty.

**Independent Test**: Open the public experience signed out, choose a role, provide the required
application details and resume, submit, and move a synthetic application through each candidate
status while verifying the candidate-facing language and notification preference.

**Acceptance Scenarios**:

1. **Given** a public visitor, **When** they open a shared role page, **Then** they can review open
   roles, role essentials, the recruitment process, and privacy expectations without signing in.
2. **Given** a valid quick application, **When** it is submitted, **Then** the candidate receives a
   confirmation identifying the role and the next expected step.
3. **Given** an invalid or incomplete application, **When** submission is attempted, **Then** errors
   identify the affected fields and no duplicate or partial application is created.
4. **Given** an application status update, **When** the candidate views progress, **Then** one of
   Applied, Profile viewed, Shortlisted, Recruiter interested, Interview requested, Offer made, Not
   selected, or Withdrawn is presented in plain language with its update time.
5. **Given** the candidate has enabled email, WhatsApp, both, or neither, **When** a status changes,
   **Then** the confirmation accurately states which notification channels will be used.
6. **Given** a candidate with an existing verified-email profile, **When** they apply to another
   role, **Then** the system links a new application to that profile without overwriting the status,
   answers, consent context, timestamps, notes, or audit history of any earlier application.
7. **Given** a recruiter confirms a candidate-facing status, **When** the update is published,
   **Then** the candidate sees the confirmed status and only the confirmed notification channels
   receive a message; an unconfirmed suggestion remains invisible to the candidate.
8. **Given** a verified candidate withdraws an application, **When** the withdrawal is confirmed,
   **Then** that application publishes Withdrawn without changing any other application.

---

### User Story 7 - Recruiter Organizes Hiring Work (Priority: P3)

An authorized recruiter works within a platform-provisioned tenant, creates a business-unit
context, adds openings and candidate records, launches searches for an opening, and reopens saved
searches.

**Why this priority**: Structured role context and saved searches support repeat recruiting work but
are not required for the first ad-hoc candidate search.

**Independent Test**: Within a synthetic platform-provisioned tenant, create a business-unit
context, add an opening and synthetic candidate, run a search tied to the opening, then reopen the
saved search with its criteria and result context.

**Acceptance Scenarios**:

1. **Given** an authorized recruiter in a platform-provisioned tenant, **When** they create a
   business-unit context and opening with required names, **Then** the opening appears within that
   tenant and business unit with its description, job requirements, and optional reference profile;
   the recruiter cannot create or change the tenant boundary.
2. **Given** a complete synthetic candidate entry, **When** it is saved, **Then** it becomes eligible
   for later searches and remains distinguishable from candidate-submitted data.
3. **Given** an opening, **When** the recruiter starts a search from it, **Then** the opening context
   is retained as the sole authoritative `criteria.context.opening_id` with the search and results.
4. **Given** a saved search, **When** it is reopened, **Then** its prompt, criteria, opening context,
   results, and candidate statuses are restored or changes since saving are clearly identified; it
   contains no independent top-level `opening_id`.
5. **Given** a Tenant Admin or Platform Security Admin, **When** they perform an administrative
   action, **Then** only permissions assigned to that fixed role are available and the action is
   recorded with actor, tenant, target, reason where required, outcome, and time.

### Edge Cases

- A resume has an accepted filename extension but cannot be read, is empty, password-protected,
  exceeds the published size limit, or contains unsafe content.
- Resume extraction yields conflicting values, low-confidence values, no email, or information for
  a person other than the uploading candidate.
- A candidate changes a previously visible profile to matching-roles-only or not-looking while a
  recruiter has it open, saved, or selected for comparison.
- Required consent is withdrawn after profile creation or application submission.
- A candidate becomes active after receiving a retention-expiry notice, or an active hiring process
  or documented legal hold extends beyond the profile's normal expiry date.
- A candidate requests deletion while an application is active or a documented legal hold covers
  only part of the record, cannot complete step-up verification, loses access to an export link, or
  disputes a pending, held, failed, or partially completed rights request.
- A candidate enters zero experience, fractional experience, an invalid date, a past or unexpected
  availability date, malformed profile links, or compensation text without a recognizable value.
- A recruiter prompt is empty, extremely long, contains contradictory constraints, requests more
  results than allowed, includes unknown locations or skills, or combines exclusions with required
  criteria for the same attribute.
- Matching-any and matching-all modes produce the same count, zero results, or a large difference.
- Candidate data needed for a filter or comparison is unknown, stale, or self-reported.
- A selected comparison candidate disappears because of a status filter, visibility change, or
  updated search criteria.
- A recruiter attempts to access a protected route after sign-out or from a stale saved link.
- A user changes tenant or role, attempts a guessed object identifier, loses access during an open
  session, or requests a privileged action without the required approval and reason.
- A user belongs to more than one tenant, follows a shared or stale link into another tenant,
  attempts a bulk export spanning tenants, or tries to reuse consent granted for a different
  company or recruiting purpose.
- A modal opens from a control near the end of a long result list, is closed with Escape, or is
  interrupted by navigation.
- A note or status save fails, is repeated, or conflicts with a newer update.
- The same verified email is used for concurrent applications, a candidate changes their verified
  email, or two existing profiles are discovered to belong to the same person.
- Contact or notification channels are unavailable, blocked, or not consented to.
- A regional service interruption occurs, recovery uses a backup containing later-deleted or
  consent-withdrawn records, or launch load reaches or exceeds the stated tenant, profile, or
  concurrent-user capacity.
- An attacker rotates identities or networks, a shared corporate network reaches a limit because of
  legitimate users, or a user repeatedly requests verification, uploads, applications, searches,
  or exports just below an individual threshold.
- No companies, openings, recent searches, saved searches, candidates, or results exist.
- Names, companies, roles, skills, and validation messages are substantially longer than the
  examples in the mockup.
- The experience is used at 320 CSS pixels, 200% zoom, with a keyboard, reduced motion, high
  contrast, or assistive technology.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide distinct signed-out entry points for recruiter access and the
  public candidate experience.
- **FR-002**: The system MUST restrict recruiter workspaces to authenticated, authorized recruiter
  identities and MUST return signed-out or unauthorized access attempts to sign-in with an
  explanation.
- **FR-003**: Recruiter sign-in MUST require a syntactically valid, verified work email and MUST
  reject unsupported personal email identities without revealing whether a specific account exists.
- **FR-004**: A recruiter MUST be able to sign out from every protected recruiter screen; signing
  out MUST prevent continued access to protected data through navigation history or a saved route.
- **FR-005**: An authenticated recruiter MUST be able to enter, edit, and submit a natural-language
  hiring prompt or populate it from a suggested or recent search.
- **FR-006**: The system MUST interpret supported prompts into visible criteria including result
  limit, location, experience range, skills, required evidence, alternative signals, preferences,
  side filters, and exclusions. Criteria MUST be organized into explicit groups with stable IDs and
  an `ANY` or `ALL` operator, and every criterion MUST have its own stable ID and reference exactly
  one existing group; unsupported concepts MUST remain visible as unrecognized rather than being
  silently ignored.
- **FR-007**: The system MUST send clear prompts directly to results and MUST route ambiguous or
  materially incomplete prompts through a review state.
- **FR-008**: During criteria review, recruiters MUST be able to add, edit, and remove requirements,
  preferences, exclusions, criteria groups, and group membership and choose `ANY` or `ALL` for each
  group without changing an existing group's stable ID.
- **FR-009**: Criteria review MUST show the original prompt, every active group and stable ID, each
  criterion's group and purpose, requested result limit, and the estimated impact of each group's
  `ANY` versus `ALL` operator before search.
- **FR-010**: Search execution MUST reject duplicate group or criterion IDs and criteria that
  reference a missing group, apply every visible group with its confirmed `ANY` or `ALL` semantics,
  use preference groups only to influence ordering, apply exclusion groups deterministically, cap
  results at the requested limit, and produce a stable order when relevance is equal.
- **FR-011**: Every ranked result MUST disclose its principal supporting evidence, relevant unknown
  or self-reported values, and material reasons its score is lower than stronger matches.
- **FR-012**: The system MUST NOT use protected characteristics or obvious proxies as search,
  filtering, or ranking inputs, and a match score MUST NOT make or imply a final hiring decision.
- **FR-013**: The results view MUST support an all-status view, status-specific filtering, result
  criteria editing, matching-mode changes, and a recoverable no-results state.
- **FR-014**: Each result card MUST present identity, current role and company, location,
  experience, notice or availability, compensation availability, freshness, skills, relevant
  stage signals, current recruiting status, and whether the profile was previously viewed.
- **FR-015**: Recruiters MUST be able to open a candidate detail view containing overview, resume,
  contact information permitted by candidate consent, experience timeline, evidence provenance,
  verification state, unknowns, match strengths and limitations, private notes, and actions.
- **FR-016**: Opening a profile MUST mark it as viewed without changing the candidate's recruiting
  status or visibility.
- **FR-017**: Recruiters MUST be able to save a private note for a candidate within the authorized
  tenant and recruiting context and receive success or failure feedback. A sourced candidate's note
  MUST belong to a candidate-work record; an application's note MUST remain in that application's
  context. Private notes MUST never appear to candidates or unauthorized recruiters.
- **FR-018**: Recruiters MUST be able to assign the supported recruiting statuses Sourced,
  Shortlisted, Contacted, Screening, Interviewing, Offered, Rejected, Not relevant, and Hired.
- **FR-019**: Internal recruiting status MUST remain associated with its candidate-work or
  application context and the relevant opening or search. Changing it to Shortlisted MUST keep the
  same context's comparison and shortlist state consistent without modifying another context.
- **FR-020**: Selecting Not relevant MUST request one or more structured reasons or an explanatory
  note before confirmation; cancellation MUST restore the prior status.
- **FR-021**: Recruiters MUST be able to select candidates for comparison and view consistent,
  side-by-side fields and match reasons; unknown data MUST be explicitly labeled.
- **FR-022**: Contact and team-sharing actions MUST identify the destination, disclose only the
  minimum permitted candidate data, respect visibility and consent at action time, and confirm the
  outcome or failure.
- **FR-023**: Every search MUST declare context `AD_HOC` or `OPENING`. An `OPENING` search MUST
  reference an active `opening_id`; an `AD_HOC` search MUST NOT carry an `opening_id`. The recruiter
  experience MUST retain up to six recent `AD_HOC` searches with enough context to rerun them and
  MUST distinguish them from `OPENING` searches saved to an opening. For executed, recent, and saved
  searches, `criteria.context.opening_id` MUST be the sole authoritative opening context; clients and
  API representations MUST NOT supply or expose an independent top-level `opening_id`.
- **FR-024**: Within an existing platform-provisioned tenant, authorized recruiters MUST be able to
  create synthetic business-unit contexts, openings, and recruiter-entered candidate records with
  explicit source labels and reopen searches saved for an opening. Recruiters MUST NOT create,
  merge, split, or change tenant boundaries.
- **FR-025**: The public candidate platform MUST be usable without an internal recruiter account
  and MUST explain the profile contents, candidate controls, consent purpose, and post-submission
  process before publication.
- **FR-026**: Candidates MUST be able to upload PDF, DOC, or DOCX resumes within a published size
  limit; the system MUST reject unsupported, unreadable, empty, password-protected, oversized, or
  unsafe files without losing other form entries.
- **FR-027**: Resume processing MUST show idle, reading, success, partial, and failure states and
  MUST label extracted values and confidence or missing status for candidate review.
- **FR-028**: Resume extraction MUST NOT invent data from a filename or uncertain content, MUST NOT
  overwrite a candidate's deliberate edits without confirmation, and MUST allow every extracted
  value to be corrected before publication.
- **FR-029**: Candidate profile submission MUST require a resume, full name, valid email, location,
  experience, skills, a visibility choice, and affirmative recruitment consent.
- **FR-030**: Current role, company, professional links, notice or availability, last working day,
  compensation, phone or WhatsApp, opportunity preferences, work arrangement, and meaningful-work
  narrative MUST remain optional unless a selected role has a separately disclosed necessity.
- **FR-031**: The meaningful-work narrative MUST accept no more than 300 characters and MUST show a
  live count without preventing access to its label or instructions.
- **FR-032**: Candidates MUST be able to select Approved recruiters, Matching roles, Applied roles
  only, or Not looking, plus Flexible, Remote, Hybrid, or On-site work preference. The system MUST
  explain the audience and consequence of each visibility selection before saving and MUST enforce
  the current selection on every search, profile, comparison, contact, share, export, saved result,
  application, and notification access. `APPROVED_RECRUITERS` MUST include a non-empty explicit
  authorized audience, and `MATCHING_ROLES` MUST include deterministic matching preferences.
- **FR-033**: Before publishing, the system MUST show profile completion, identify every missing or
  invalid required value, focus the first error on request, and preserve all valid candidate input.
- **FR-034**: Submitting a visible profile MUST show a confirmation and make it discoverable only to
  its permitted audience; saving Not looking right now MUST confirm non-discoverability.
- **FR-035**: Candidates MUST be able to view open role essentials and submit a quick application
  containing name, valid email, selected role, supported resume, and consent without an internal
  account.
- **FR-036**: A successful application MUST have one candidate-facing status from Applied, Profile
  viewed, Shortlisted, Recruiter interested, Interview requested, Offer made, Not selected, or
  Withdrawn and MUST display when the status was last updated.
- **FR-037**: Candidates MUST be able to choose email and WhatsApp update preferences independently;
  status changes MUST accurately confirm which selected channels will receive an update.
- **FR-038**: User-entered data, search state, notes, selection, filters, and status changes MUST not
  be lost on an ordinary refresh after a successful save, and any unsaved-loss risk MUST be warned
  before navigation.
- **FR-039**: Every asynchronous or externally handed-off action MUST expose pending, success,
  empty, unavailable, and error outcomes as applicable and MUST provide a retry or safe fallback.
- **FR-040**: Existing workflows and state transitions represented by the approved mockup MUST be
  preserved unless a later approved specification explicitly changes them.
- **FR-041**: The system MUST maintain one candidate-controlled profile per verified email and MUST
  link a separate application for each role. Profile updates MAY update shared candidate facts but
  MUST NOT overwrite any application's status, role-specific answers, consent context, timestamps,
  notes, or audit history.
- **FR-042**: An internal recruiter status change MUST NOT directly publish a candidate-facing
  status or notification. The system MAY suggest Applied after submission, Profile viewed after the
  first authorized view, Shortlisted after internal shortlisting, Recruiter interested after
  Contacted or Screening, Interview requested after Interviewing, Offer made after Offered, and Not
  selected after Rejected. A verified candidate MAY publish Withdrawn by explicitly confirming an
  application withdrawal.
  Before publication, the recruiter MUST preview and explicitly confirm the candidate-facing
  wording, audience, and notification channels. Internal statuses without a semantically equivalent
  candidate-facing status MUST produce no suggestion and MUST leave the published status unchanged.
- **FR-043**: Launch authorization MUST use five fixed least-privilege roles: Candidate may manage
  only their own profile and applications; Recruiter may perform recruiting work only within an
  assigned tenant and permitted objects; Hiring Manager may view only explicitly shared openings
  and candidate records and MUST NOT see private recruiter notes, contact details, or compensation
  unless separately permitted; Tenant Admin may manage tenant users, role assignments, settings,
  and audit access but receives no automatic candidate-content access; Platform Security Admin may
  perform security administration but receives no standing candidate-content access.
- **FR-044**: Every protected data read, write, search, export, share, administrative action, and
  externally initiated operation MUST verify the authenticated actor's role, tenant membership,
  object permission, and current candidate consent before returning data or changing state. A
  hidden control or previously valid link MUST NOT substitute for authorization.
- **FR-045**: Platform Security Admin access to candidate content MUST be an emergency access grant
  that is automatically time-limited, tied to a stated justification and incident or support
  reference, explicitly approved by a different designated Platform Security Admin who is not the
  requester, limited to the necessary tenant, objects, fields, and read operations, revocable by an
  authorized Platform Security Admin or affected Tenant Admin, and fully audited. The approval MUST
  confirm the exact tenant, object, field, read-operation, justification, and expiry scope before
  activation. Activation MUST immediately notify the affected Tenant Admins without granting them
  candidate-content access. Activation, use, expiry, revocation, denial, and failed access MUST be
  audited. Expired, rejected, over-scoped, self-approved, or revoked grants MUST fail closed on every
  request. A request with an empty `field_scope` MUST be rejected before approval or activation.
- **FR-046**: The platform MUST maintain one candidate-controlled profile governed by that
  candidate's visibility and consent settings while strictly isolating each tenant's openings,
  applications, searches, statuses, notes, shortlists, exports, communications, and audit records.
  A user with multiple tenant memberships MUST act within one explicit tenant context at a time.
- **FR-047**: Cross-tenant candidate-data disclosure MUST be denied by default and MUST require
  explicit, purpose-specific candidate consent plus current tenant- and object-level authorization.
  Consent for one tenant, opening, or purpose MUST NOT be reused for another, and every permitted
  disclosure MUST be recorded in both the candidate's disclosure history and the receiving tenant's
  audit history.
- **FR-048**: Launch rate limits MUST apply to both verified-identity and network signals: no more
  than 5 failed sign-in attempts per identity and network in 15 minutes; 5 verification codes per
  address and 20 per network per hour; 10 resume uploads per verified candidate per hour; 20
  applications per candidate per day; 60 searches per recruiter per minute; and 5 exports per
  authorized user per hour. Meeting one limit MUST NOT bypass another applicable limit.
- **FR-049**: Limit violations MUST use escalating temporary delays and provide a safe retry time
  without confirming account existence. Anomalous distributed or near-threshold behavior MUST
  permit temporary tightening, step-up verification, or suspension of the affected operation, but
  MUST NOT cause permanent automatic lockout. Every block, challenge, rule change, and authorized
  override MUST record actor or signal, tenant where applicable, rule, reason, duration, outcome,
  and approving authority without storing unnecessary sensitive request content.
- **FR-050**: Consent, visibility, recruiting status, recruiter note, and administrative-setting
  writes MUST use optimistic conflict detection. A stale write MUST be rejected without changing
  stored data and MUST present the latest authorized stored state, the user's attempted changes,
  and the changed fields so the user can explicitly discard, reconcile, or resubmit the update.
- **FR-051**: Identity, authorization, primary-data, and file-security uncertainty or failure MUST
  fail closed. Resume-parsing failure MUST preserve the candidate's other valid input and offer
  manual profile entry, but no resume content or download MUST be exposed until security scanning
  has succeeded.
- **FR-052**: Notifications MUST be queued with a unique idempotency key, retried no more than five
  delivery attempts within 24 hours, moved to dead-letter handling after terminal failure, and
  represented internally as `QUEUED`, `SENDING`, `SENT`, `FAILED`, or `CANCELLED`. Candidate-facing
  APIs and views MUST expose only `PENDING`, `SENT`, `FAILED`, or `CANCELLED`, mapping both internal
  `QUEUED` and `SENDING` to `PENDING`, without implying delivery that has not been confirmed.
- **FR-053**: Every Tenant Admin and Platform Security Admin access decision and action MUST record
  the authenticated actor, effective role, tenant where applicable, target, action, reason and
  approval or grant when required, outcome, time, and correlation context. Administrative audit
  records MUST exclude unnecessary candidate content, be separately access-controlled, and record
  access to the audit history itself.
- **FR-054**: A verified candidate MUST have a self-service rights center for access, correction,
  consent withdrawal, profile hiding, export, and deletion. Access and correction MUST take effect
  immediately after successful validation; consent withdrawal and profile hiding MUST take effect
  immediately across new search, comparison, sharing, contact, and export access.
- **FR-055**: A candidate export MUST be generated within 24 hours of a verified request, contain
  the candidate's authorized profile, consent, disclosure, application, status, and communication
  history in a documented portable format, and be available through an encrypted, authenticated
  download that expires after 24 hours. Expired, failed, or incomplete exports MUST support a safe
  retry or support escalation without exposing a partial artifact.
- **FR-056**: Candidate-requested deletion MUST require recent step-up identity verification, a clear
  consequence preview, and explicit confirmation. Confirmation MUST immediately hide the profile
  and revoke optional processing; deletion MUST complete within 30 days except for the minimum data
  covered by a clearly identified active hiring process or documented legal hold. The system MUST
  identify the affected scope and reason to the candidate without revealing protected internal or
  third-party information, resume deletion when the exception ends, and never treat an exception as
  permission for unrelated processing. Before real candidate data is enabled, an approved,
  versioned retention policy MUST enumerate which internal application or candidate-work states
  constitute an active hiring process, the exact data each state may retain, its mandatory review
  date, and the event that ends the exception; a candidate-facing status alone MUST NOT create or
  extend an exception. Every active-process exception MUST be a versioned
  `ActiveProcessRetentionException` containing the candidate and application reference, policy
  version, legal basis, retained-data scope, lifecycle state, start date, review date, terminating
  event, resolution date when resolved, approver, and audit references.
- **FR-057**: The rights center MUST show each request's type, submitted time, scope, state, expected
  completion time, completion or exception details, and available next action using `PENDING`,
  `IN_PROGRESS`, `HELD`, `COMPLETED`, `FAILED`, or `CANCELLED`. Candidates MUST be able to escalate a
  failed, disputed, inaccessible, or overdue request to support, and every request, transition,
  download, exception, and support action MUST be audited without copying unnecessary candidate data.
- **FR-058**: Only a valid `OPENING` search with an active `opening_id` MAY discover candidates under
  `MATCHING_ROLES`, and it MUST require deterministic satisfaction of the candidate's selected role
  categories, locations, work arrangements, and any other candidate-designated eligibility
  preferences. An `AD_HOC` search MAY access only candidates whose `APPROVED_RECRUITERS` audience
  authorizes the tenant and MUST never bypass candidate preferences. AI-generated scores,
  embeddings, inferences, or explanations MAY order already eligible results but MUST NOT make an
  otherwise ineligible candidate discoverable.
- **FR-059**: Under Applied roles only visibility, a profile MUST be absent from sourcing searches
  and MUST be disclosed only to a currently authorized hiring team for an application the candidate
  submitted, within that application's tenant, opening, purpose, field, and lifecycle scope.
- **FR-060**: The only candidate-facing application statuses MUST be `APPLIED`, `PROFILE_VIEWED`,
  `SHORTLISTED`, `RECRUITER_INTERESTED`, `INTERVIEW_REQUESTED`, `OFFER_MADE`, `NOT_SELECTED`, and
  `WITHDRAWN`. A successful candidate submission MUST publish `APPLIED`. First authorized view MAY
  suggest `PROFILE_VIEWED`; internal Shortlisted MAY suggest `SHORTLISTED`; Contacted or Screening
  MAY suggest `RECRUITER_INTERESTED`; Interviewing MAY suggest `INTERVIEW_REQUESTED`; Offered MAY
  suggest `OFFER_MADE`; and Rejected MAY suggest `NOT_SELECTED`. Every recruiter-originated
  suggestion MUST remain unpublished and unnotified until recruiter preview and explicit
  confirmation. Candidate-confirmed withdrawal publishes `WITHDRAWN`. Sourced, Not relevant, Hired,
  and every other unmapped internal state MUST set `suggested_candidate_status` to null and MUST
  leave the published status unchanged. A status-preview request MUST accept one
  `InternalRecruitingStatus` and map it to either a nullable `CandidateFacingStatus` suggestion or
  null. A status-publication request MUST accept only the approved eight-value
  `CandidateFacingStatus` enum and MUST require explicit recruiter confirmation. An unmapped
  internal status MUST NOT be published unless the recruiter explicitly selects and confirms a
  valid `CandidateFacingStatus`.
- **FR-061**: When an authorized recruiter first views, notes, shortlists, or changes the internal
  status of a sourced candidate who has no application, the system MUST create or reuse exactly one
  tenant-scoped candidate-work record for that candidate and originating search, with an optional
  opening. The record MUST retain its own internal status, private notes, shortlist state, structured
  reasons, timestamps, actor history, and audit history. A later application MAY link to the
  candidate-work record but MUST NOT merge, copy implicitly, or overwrite either record's status,
  notes, reasons, consent context, timestamps, or audit history.
- **FR-062**: One tenant MUST represent one contracted customer company or legally separate
  recruiting boundary. Only the platform-onboarding function, operated by authorized platform
  personnel under audited procedure, MAY provision, merge, split, suspend, reactivate, or close a
  tenant. Business units MUST remain tenant-owned organizational contexts and MUST NOT weaken or
  create a new data-isolation boundary.
### Interaction and State Requirements

- **ISR-001**: Global navigation MUST show the current area and signed-in identity, and protected
  recruiter navigation MUST not appear actionable to a signed-out candidate.
- **ISR-002**: The search side panel MUST expose collapsed, expanded, empty, and populated states;
  its controlling button MUST communicate the current state.
- **ISR-003**: Voice search MUST expose unavailable, permission-denied, listening, transcribing,
  ready-to-search, and failed states without auto-submitting speech.
- **ISR-004**: Results MUST distinguish initial, loading, populated, filtered, no-result, and failed
  states while preserving the active prompt and criteria.
- **ISR-005**: Candidate detail, comparison, missing-information, and not-relevant dialogs MUST have
  a visible title, explicit close action, predictable outside-click policy, and restoration of focus
  to the invoking control.
- **ISR-006**: Candidate upload MUST progress through no-file, reading, extracted-complete,
  extracted-partial, invalid-file, processing-failed, and ready-to-submit states.
- **ISR-007**: Success confirmations MUST state what changed, who can see it, and the next available
  action; errors MUST state what did not change and how the user can recover.
- **ISR-008**: Destructive or consequential changes, including hiding a profile, withdrawing
  consent, rejecting a candidate, or sharing candidate data, MUST communicate consequences before
  confirmation and remain recoverable where business rules permit.
- **ISR-009**: A suggested candidate-facing status MUST be visually and programmatically distinct
  from a published status and MUST remain editable or dismissible until explicit confirmation.

### Validation Rules

- **VR-001**: Required text values MUST reject empty or whitespace-only input.
- **VR-002**: Email values MUST use a valid email structure; recruiter email MUST additionally meet
  work-identity eligibility, while candidate email MUST remain distinct from recruiter access.
- **VR-003**: Experience MUST accept zero for freshers, allow documented fractional years, reject
  negative or non-numeric values, and preserve the candidate's displayed unit.
- **VR-004**: Compensation values, when provided, MUST identify currency and period; unparsable
  values MUST remain user-visible for correction and MUST not be converted to zero.
- **VR-005**: Last working day MUST be optional and MUST be checked for consistency with the selected
  availability state without blocking legitimate exceptions.
- **VR-006**: LinkedIn, portfolio, and GitHub values, when provided, MUST be valid safe web links;
  unsafe schemes MUST be rejected.
- **VR-007**: A profile or application MUST NOT be published without affirmative, specific
  recruitment consent, and consent errors MUST link to the consent control.
- **VR-008**: Validation MUST occur at submission and may occur after field interaction; it MUST not
  erase input, depend on colour alone, or announce errors before a user has had a chance to act.
- **VR-009**: Repeated submission while an action is pending MUST create at most one profile,
  application, note, status update, business-unit context, or opening record.
- **VR-010**: `MATCHING_ROLES` eligibility MUST require deterministic matching preferences and an
  `OPENING` search whose `opening_id` resolves to an active opening at execution time; an `AD_HOC`
  search MUST reject any `opening_id` property and MUST evaluate only `APPROVED_RECRUITERS`
  visibility. `criteria.context.opening_id` is the sole authoritative opening context. Any database
  opening foreign key retained for indexing MUST be server-derived and read-only, MUST be null for
  `AD_HOC`, and MUST equal `criteria.context.opening_id` for `OPENING`.
- **VR-011**: `APPROVED_RECRUITERS` visibility MUST reject an empty authorized-audience list, and
  `MATCHING_ROLES` visibility MUST reject absent or empty deterministic matching preferences.
- **VR-012**: A deletion request MUST reject absent or stale step-up verification and MUST require
  `confirm_consequences=true`; proof freshness and consequence confirmation MUST be rechecked by the
  service even when the request conforms to the API schema.
- **VR-013**: An emergency-access request MUST reject an absent or empty `field_scope` before it can
  be approved or activated.
- **VR-014**: Search criteria MUST reject missing, duplicate, or unstable group/criterion IDs,
  operators other than `ANY` or `ALL`, and any criterion whose `group_id` does not resolve to exactly
  one group in the same search definition.
- **VR-015**: Status preview MUST reject values outside `InternalRecruitingStatus` and return either
  a valid `CandidateFacingStatus` suggestion or null. Status publication MUST reject values outside
  `CandidateFacingStatus`, and a null suggestion MUST NOT be published unless the recruiter supplies
  and explicitly confirms a valid candidate-facing value.

### Accessibility and Responsive Requirements

- **AR-001**: All recruiter and candidate workflows MUST conform to WCAG 2.2 Level AA.
- **AR-002**: Every interactive element MUST be reachable and operable by keyboard in a logical
  order, with a visible focus indicator and no keyboard trap.
- **AR-003**: Controls MUST expose programmatic names, roles, values, expanded/selected/invalid
  states, and relationships to labels, descriptions, errors, and controlled regions.
- **AR-004**: Search results, upload progress, validation summaries, save confirmations, status
  changes, and speech states MUST be announced without unexpectedly moving focus.
- **AR-005**: Dialogs MUST move focus to an appropriate starting element, contain focus while open,
  close with Escape unless doing so would lose unsaved work, and return focus to their invoker.
- **AR-006**: Meaning MUST not depend only on colour, placement, icons, hover, animation, or pointer
  precision; tooltips MUST also be available through focus and persistent text where essential.
- **AR-007**: Content and core actions MUST remain usable at 200% zoom and from 320 CSS pixels through
  large desktop widths without horizontal page scrolling or hidden controls.
- **AR-008**: Cards, filters, forms, navigation, timelines, evidence tables, dialogs, and comparison
  views MUST reflow without changing their reading order or concealing decision-relevant content.
- **AR-009**: Touch targets MUST be large and separated enough for reliable activation, and hover
  behavior MUST have touch and keyboard equivalents.
- **AR-010**: Motion MUST respect reduced-motion preferences, and timed feedback MUST remain long
  enough to perceive or be available persistently elsewhere.

### Privacy and Data Requirements

- **PR-001**: The current prototype and all specification test data MUST use synthetic identities,
  resumes, contact details, compensation, notes, and applications only.
- **PR-002**: Candidate data MUST be collected only for a disclosed recruiting purpose and limited
  to information necessary for the active profile or application workflow.
- **PR-003**: Candidate visibility and consent MUST be enforced in search, profile, comparison,
  contact, sharing, export, saved results, and recruiter-entered records, not merely hidden in the
  interface.
- **PR-004**: Contact details, resumes, compensation, availability, private recruiter notes, and
  application history MUST be restricted to authorized audiences and MUST not appear in URLs,
  analytics, public errors, or screenshots used as fixtures.
- **PR-005**: Before real data is accepted, verified candidates MUST be able to use a self-service
  rights center to access and correct data immediately, withdraw consent or hide their profile
  immediately, receive an export within 24 hours through an authenticated link that expires after
  24 hours, and request deletion using step-up verification and explicit confirmation. Deletion MUST
  hide the profile immediately and complete within 30 days except for clearly identified active-
  process or legal-hold data; request status and support escalation MUST remain available.
- **PR-006**: Before launch or migration of real candidate data, the system MUST implement and pass
  review for retention, deletion, encryption, access control, access review, audit history,
  candidate-rights requests, backup handling, and incident response.
- **PR-007**: Match explanations MUST distinguish candidate-supplied facts, resume-derived evidence,
  recruiter-entered notes, system inferences, and unknown values.
- **PR-008**: The initial production launch MUST be limited to India-based recruitment and candidate
  data within the approved India compliance scope. Expansion to another jurisdiction or a
  cross-border processing arrangement MUST be blocked until a documented privacy, employment,
  transfer, and candidate-rights review is approved.
- **PR-009**: An inactive candidate profile MUST expire 12 months after its last qualifying
  candidate or recruiting activity. The candidate MUST receive a renewed-consent request 30 days
  before expiry. Without renewed consent, the identifiable profile and resume MUST be deleted when
  the period ends; only irreversibly anonymized analytics MAY remain. An active hiring process or
  documented legal hold pauses deletion only for its necessary, recorded duration, after which the
  normal deletion review MUST resume.
- **PR-010**: Restored data MUST remain inaccessible to ordinary users until all deletion,
  consent-withdrawal, tenant-access revocation, and emergency-access revocation events through the
  recovery point have been reapplied and verified. Backup expiry MUST permanently remove recoverable
  copies after the approved 35-day period unless a documented legal hold applies.

### Key Entities *(include if feature involves data)*

- **Recruiter**: An authorized hiring user with work identity, display name, permissions, and
  access to recruiter-only searches, candidate data, notes, and actions.
- **Authorization Role and Assignment**: One of Candidate, Recruiter, Hiring Manager, Tenant Admin,
  or Platform Security Admin, associated with an identity, tenant where applicable, permitted
  objects, effective time, expiry or revocation state, and assigning authority.
- **Tenant**: One platform-provisioned contracted customer company or legally separate recruiting
  boundary with its own users, roles, business units, openings, applications, searches, statuses,
  notes, shortlists, exports, communications, settings, and audit records. Business units are
  organizational contexts inside the tenant, not isolation boundaries. A tenant has no implicit
  access to another tenant's records.
- **Candidate Profile**: The single candidate-controlled identity associated with one verified
  email, including role and company, location, experience, skills, professional links,
  availability, compensation preferences, work preferences, visibility, meaningful-work narrative,
  provenance, verification state, freshness, last qualifying activity, retention-expiry date, and
  any recorded retention exception. It can relate to multiple applications.
- **Resume**: A candidate-provided document with filename, supported type, processing state,
  extracted fields, confidence/provenance, and candidate corrections; it remains separate from the
  published profile.
- **Consent and Visibility Preference**: The candidate's affirmative purpose-specific consent;
  current `APPROVED_RECRUITERS`, `MATCHING_ROLES`, `APPLIED_ROLES_ONLY`, or `NOT_LOOKING` visibility;
  deterministic candidate-controlled matching preferences where applicable; contact preferences;
  effective time; and any later withdrawal.
- **Hiring Search**: The original prompt, parsed criteria groups, match mode, result limit, opening
  context type (`AD_HOC` or `OPENING`), active `opening_id` when required, created time, and whether
  it is recent or explicitly saved. Each group has a stable ID, purpose, and `ANY`/`ALL` operator;
  each criterion has a stable ID and references exactly one group. The only authoritative opening
  reference is `criteria.context.opening_id`; saved-search APIs contain no independent opening field.
- **Search Result**: A candidate's position for a specific search, relevance outcome, supporting
  reasons, limiting reasons, unknowns, and evidence provenance.
- **Recruiting Status**: A recruiter's workflow state for a candidate within a search or opening,
  including update time and authorized updater.
- **Candidate Work Record**: A tenant-owned recruiting context for a sourced candidate, created on
  first authorized view, note, shortlist, or internal status change and linked to one originating
  search and an optional opening. It owns its internal status, private notes, shortlist state,
  structured reasons, timestamps, actors, and audit history and may link to, but never merge with,
  a later application.
- **Recruiter Note**: Private recruiter-authored content associated with a candidate and restricted
  to authorized recruiter audiences within one candidate-work or application context.
- **Comparison Selection**: The candidates selected within the current result context and the
  common fields used for side-by-side review.
- **Not-Relevant Feedback**: Structured reasons, optional note, candidate, search context, and time
  captured to improve search quality.
- **Audit Event**: An append-only record of actor, role, tenant, target object, action, outcome,
  timestamp, source context, approval and reason where required, and correlation to an incident or
  support reference without copying sensitive candidate content unnecessarily.
- **Business Unit and Job Opening**: Tenant-owned hiring context containing business-unit details,
  role description, requirements, optional reference profile, and related saved searches. It never
  creates or changes the tenant boundary.
- **Application**: A role-specific submission linked to one candidate profile and one job opening,
  with its own answers, resume reference or version, consent context, internal recruiter status,
  nullable suggested candidate-facing status, published candidate-facing status limited to Applied,
  Profile viewed, Shortlisted, Recruiter interested, Interview requested, Offer made, Not selected,
  or Withdrawn, recruiter notes,
  update preferences, timestamps, status history, and audit history. Applications for different
  roles remain separate even when they share a candidate profile and are owned by exactly one tenant.
- **Candidate Rights Request**: A verified candidate's access, correction, consent-withdrawal,
  profile-hiding, export, or deletion request, including scope, step-up verification where required,
  submitted and target times, current state, active-process or legal-hold exception, expiring export
  artifact, completion evidence, support escalation, and audit history.
- **Active Process Retention Exception**: A versioned, approved exception for the minimum data
  retained during a defined active hiring process, containing candidate and application references,
  policy version, legal basis, retained-data scope, lifecycle state, start/review dates, terminating
  event, resolution date, approver, and audit references.

### Scope Boundaries

**In scope**:

- The recruiter and candidate journeys, content, interactions, states, and responsive behavior
  represented by the existing mockup.
- Ad-hoc and opening-linked recruiter search; criteria review; ranking explanations; results,
  filtering, profiles, comparison, notes, contact/share handoffs, and status management.
- Candidate resume-led profile creation, privacy preferences, public role discovery, quick apply,
  validation, consent, and understandable status feedback.
- Production handling of real candidate data, including authenticated access, authorization,
  encrypted transfer and storage, audit history, retention and deletion enforcement, candidate
  data-rights requests, backup treatment, and incident response.
- Initial production operation for India-based recruitment and candidate data.
- Synthetic tenant, business-unit, opening, candidate, search, and application data sufficient to
  test the full experience safely.

**Out of scope for this specification**:

- Selecting an implementation architecture, programming language, framework, storage product,
  parsing provider, messaging provider, or authentication vendor.
- Making autonomous hiring decisions or replacing human recruiter review.
- Defining organization-wide recruiting policy or employment-law rules beyond this feature's
  approved India privacy and retention scope; those require separate owner review.
- Processing candidate data outside the approved India launch scope or enabling cross-border data
  transfers without a separately approved expansion.
- Implementing or changing the existing HTML mockup in this phase.
- Accepting real people as recruiter-entered candidate records; launch recruiter-entered records are
  visibly synthetic tenant fixtures only, and real recruiter-entered sourcing requires a separate
  privacy-reviewed specification.
- AI-generated comparison summaries or recommendations; launch comparison is deterministic,
  evidence-based, and human reviewed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90% of representative candidates can complete a valid synthetic resume-led
  profile on their first attempt without facilitator help.
- **SC-002**: A candidate with a supported resume can reach a reviewable profile preview within two
  minutes and can identify every required missing field before submission.
- **SC-003**: In moderated testing, 100% of candidates can correctly state who may see their profile
  for each visibility option before saving it.
- **SC-004**: At least 95% of valid profile and quick-application submissions create exactly one
  confirmation-visible record; invalid submissions create none and retain valid entries.
- **SC-005**: At least 90% of representative recruiters can sign in, submit a hiring need, understand
  or correct the interpreted criteria, and open a relevant candidate profile within three minutes.
- **SC-006**: For a fixed synthetic dataset, 100% of displayed results satisfy all visible strict
  criteria and exclusions, and every result presents at least one supporting reason.
- **SC-007**: At least 90% of recruiters can distinguish requirement, preference, and exclusion
  groups and correctly explain `ANY` versus `ALL` after using the criteria review once.
- **SC-008**: At least 90% of recruiters can compare two candidates, save a private note, and update
  a status without losing the active search or asking for assistance.
- **SC-009**: Every critical workflow can be completed using keyboard alone at 320 CSS pixels and at
  200% zoom, with no keyboard trap, hidden core action, or two-dimensional page scrolling.
- **SC-010**: Accessibility evaluation finds no known Level A or AA failures in the critical
  journeys and all dynamic state, validation, and dialog transitions are announced meaningfully.
- **SC-011**: Privacy tests confirm that a not-looking profile is absent from 100% of recruiter
  search, comparison, sharing, and contact surfaces and that private recruiter notes are absent
  from 100% of candidate surfaces.
- **SC-012**: In usability testing, at least 85% of participants rate search explanations, form
  errors, profile visibility, and application status as clear or very clear.
- **SC-013**: For normal user actions, visible feedback for navigation, save, filtering, and status
  changes begins within one second; operations requiring longer work continuously communicate
  progress and remain cancellable or safely retryable.
- **SC-014**: All pre-existing critical mockup workflows pass regression checks after any future
  implementation change unless an approved specification explicitly replaces that behavior.
- **SC-015**: Before any real candidate record is accepted, all production privacy controls in
  PR-006 pass documented positive and negative acceptance tests, with no unresolved critical or
  high-severity privacy or security findings.
- **SC-016**: Before production launch, 100% of candidate-facing notices, consent flows, data-rights
  procedures, retention behavior, recruiter access rules, and processing locations have documented
  approval for the India launch scope.
- **SC-017**: Retention tests confirm that 100% of inactive profiles receive a renewal request 30
  days before their 12-month expiry and, without renewal or a valid recorded exception, have all
  identifiable profile and resume data deleted at expiry while only irreversibly anonymized
  analytics remain.
- **SC-018**: Applying to multiple roles with the same verified email creates exactly one candidate
  profile and one distinct application per role, with 100% preservation of each application's
  status, answers, consent context, timestamps, notes, and audit history.
- **SC-019**: In status-transition tests, 100% of candidate-facing updates and notifications remain
  unpublished until recruiter confirmation, and each confirmed update uses only the previewed
  wording, audience, and notification channels.
- **SC-020**: Authorization tests cover every role and protected operation and demonstrate that
  100% of unauthorized cross-role, cross-tenant, and object-level attempts are denied without
  exposing candidate data or confirming whether the target exists.
- **SC-021**: Every Platform Security Admin candidate-content access test requires a valid,
  unexpired, justification-bound grant approved by a different designated Platform Security Admin,
  limited to exact tenant/object/field/read scope, immediately notified to affected Tenant Admins,
  revocable by an authorized Platform Security Admin or affected Tenant Admin, and completely
  audited; 100% of missing, self-approved, over-scoped, expired, rejected, or revoked grants are
  denied.
- **SC-022**: Tenant-isolation tests demonstrate that 100% of cross-tenant reads, writes, searches,
  exports, shared links, and guessed-object requests are denied unless matching purpose-specific
  candidate consent and authorization are active, and every permitted disclosure appears in both
  required audit histories.
- **SC-023**: Critical candidate and recruiter journeys achieve at least 99.9% availability in each
  calendar month, excluding only preannounced maintenance capped at two hours per month; all other
  unavailability counts against the target.
- **SC-024**: Disaster-recovery exercises demonstrate no more than 15 minutes of committed-data loss
  and restore critical candidate and recruiter journeys within four hours of declaring recovery.
- **SC-025**: Encrypted backups remain recoverable for 35 days, and every quarterly restore test
  verifies data integrity, tenant isolation, authorization, audit continuity, and reapplication of
  deletions, consent withdrawals, and revoked access before restored data becomes accessible.
- **SC-026**: At launch capacity of 100 tenants, 1 million candidate profiles, and 1,000 concurrent
  active users, at least 95% of normal searches complete within three seconds while authorization,
  tenant isolation, result correctness, and audit recording remain intact.
- **SC-027**: Abuse-protection tests verify every FR-048 threshold across identity and network
  signals, provide a correct safe retry time for 100% of blocked requests, expose no account
  existence, create no permanent automatic lockout, and produce complete audit events for every
  block and authorized override.
- **SC-028**: Concurrency tests reject 100% of stale consent, visibility, status, note, and
  administration writes without data loss and show the latest authorized stored state, attempted
  changes, and changed fields for explicit reconciliation.
- **SC-029**: Failure-injection tests deny protected operations during identity, authorization,
  primary-data, or file-security uncertainty; 100% of resume-parsing failures preserve manual entry
  while preventing resume access until a successful security scan.
- **SC-030**: Notification tests demonstrate that repeated or retried delivery creates no duplicate
  notification, makes no more than five delivery attempts within 24 hours, sends terminal failures
  to dead-letter handling, maps internal `QUEUED` and `SENDING` to candidate-facing `PENDING`, and
  prevents candidate-facing APIs from exposing any state other than `PENDING`, `SENT`, `FAILED`, or
  `CANCELLED`.
- **SC-031**: Administrative-access tests produce a complete minimized audit event for 100% of
  allowed, denied, failed, approved, rejected, expired, revoked, and audit-history access actions,
  with no unnecessary candidate content in the audit record.
- **SC-032**: Candidate-rights tests demonstrate that 100% of verified access and correction actions
  take effect immediately; consent withdrawal and profile hiding immediately prevent all new
  discovery and optional disclosure; complete exports are available within 24 hours and expire
  after 24 hours; and confirmed deletion hides the profile immediately and completes within 30 days
  except for precisely scoped, visible active-process or legal-hold records. Every request exposes
  the correct state and permits support escalation for failed, disputed, inaccessible, or overdue
  handling.
- **SC-033**: Visibility tests demonstrate that Approved recruiters follows the candidate's explicit
  non-empty approved audience and is the only discoverable mode in an `AD_HOC` search; Matching
  roles admits only profiles satisfying deterministic candidate preferences in a valid `OPENING`
  search for an active opening and never admits a profile solely because of an AI score; executed,
  recent, and saved search contracts expose no opening context outside `criteria.context`;
  Applied roles only is absent from 100% of unrelated sourcing searches and is accessible only to
  the authorized hiring team for a submitted application; and Not looking is absent from 100% of
  new recruiter discovery, comparison, sharing, contact, and export surfaces.
- **SC-034**: Status-contract tests demonstrate that 100% of candidate views, APIs, audit events,
  and notifications use only Applied, Profile viewed, Shortlisted, Recruiter interested, Interview
  requested, Offer made, Not selected, or Withdrawn; every recruiter-originated mapping remains
  unpublished until explicit confirmation; preview accepts `InternalRecruitingStatus`, publication
  accepts only `CandidateFacingStatus`, candidate-confirmed withdrawal is application-scoped, and
  Sourced, Not relevant, Hired, and other unmapped internal states return a null suggestion that
  cannot be published without explicit selection of a valid candidate-facing value.
- **SC-035**: Sourced-candidate workflow tests demonstrate that first authorized view, note,
  shortlist, or internal status change creates or reuses exactly one tenant-scoped candidate-work
  record for the originating search; that records with different tenants or recruiting contexts do
  not share notes or state; and that a later linked application preserves 100% of each record's
  independent status, notes, reasons, timestamps, consent context, and audit history.
- **SC-036**: Tenant-governance tests demonstrate that only audited platform onboarding can
  provision, merge, split, suspend, reactivate, or close a tenant; recruiters can create business
  units and openings only within their active tenant; business units never bypass tenant isolation;
  and 100% of recruiter or tenant-user attempts to create or alter a tenant boundary are denied and
  audited without revealing another tenant's existence or data.

## Assumptions

- The existing mockup is the approved visual and behavioral baseline for this specification, while
  requirements in the constitution take precedence where the mockup is incomplete or unsafe.
- Development, demonstration, and automated testing use synthetic data only. The released feature
  may accept real candidate data only after the production controls in PR-006 and SC-015 pass.
- Recruiter and candidate are distinct audiences. Candidates do not need an internal recruiter
  account to create a profile or apply, and recruiter-only data is never exposed publicly.
- The initial production audience and recruiting operation are India-based; support for any other
  jurisdiction or cross-border processing is a separately reviewed expansion.
- A verified work email is sufficient only for the mockup flow. Production access follows the five
  fixed roles in FR-043 and requires active tenant and object authorization where applicable.
- Clear prompts contain enough role or skill context plus search scope to run directly. Ambiguous
  prompts are reviewable rather than rejected.
- Unknown candidate data remains unknown and visible as such; the system never fills gaps merely to
  make a card, score, or comparison look complete.
- Profile visibility changes take effect immediately for new recruiter access. Handling previously
  exported data requires the separate production data-governance policy.
- Email, WhatsApp, resume parsing, malware scanning, and identity verification are external
  capabilities from the user's perspective; each may be unavailable without blocking safe access
  to unrelated workflows.
- English is the initial content language, but layouts must tolerate translated-length content and
  future localization.
- Supported browsers, resume size limits, and remaining India-specific compliance rules must be
  resolved during planning and recorded before production launch.
- The recruiter management workspace for companies, openings, and recruiter-entered candidates is
  a supporting workflow with lower priority than candidate profile creation and ad-hoc search.
