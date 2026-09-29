<!--
Sync Impact Report
- Version change: unratified scaffold -> 1.0.0
- Modified principles: placeholder principles -> I. Accessibility by Default;
  II. Responsive and Resilient Interfaces; III. Candidate Data Is Private by Design;
  IV. Clear, Usable, and Human-Centred Workflows; V. Maintainable Simplicity;
  VI. Evidence-Based Testing; VII. Preserve Existing Functionality
- Added sections: Product and Data Constraints; Delivery Workflow and Quality Gates
- Removed sections: none (placeholder sections were concretized)
- Follow-up TODOs: none
-->
# Recruiter and Candidate UX Constitution

## Core Principles

### I. Accessibility by Default
Every recruiter and candidate journey MUST meet WCAG 2.2 Level AA. All functionality MUST be
operable by keyboard, use visible focus indicators, preserve a logical focus order, expose correct
names and states to assistive technology, and avoid relying on colour, position, or motion alone.
Forms MUST have programmatically associated labels, understandable validation, and error recovery;
dynamic updates and modal dialogs MUST announce state changes and manage focus. Content MUST remain
usable at 200% zoom and with reduced motion enabled. Accessibility is a release criterion because
job access and hiring work cannot depend on a user's device or abilities.

### II. Responsive and Resilient Interfaces
Core tasks MUST work without horizontal page scrolling or lost controls from 320 CSS pixels through
large desktop widths. Layouts MUST reflow according to available space rather than named device
classes, and touch targets, typography, menus, dialogs, forms, candidate cards, comparison views,
and data-dense recruiter screens MUST remain usable at every supported breakpoint. Changes MUST be
checked with long names, translated-length text, validation messages, zoom, and both pointer and
touch input. Responsive styling MUST preserve content priority and task completion, not merely fit
the same desktop layout into a narrower viewport.

### III. Candidate Data Is Private by Design
Candidate data MUST be collected only for a stated recruiting purpose, limited to fields necessary
for that purpose, and shown only to authorized people consistent with the candidate's visibility
and consent choices. Privacy choices MUST use plain language and MUST be honored throughout search,
profile, comparison, notes, sharing, export, and deletion flows. Sensitive details such as contact
information, compensation, resumes, recruiter notes, and availability MUST have explicit access
boundaries and MUST NOT appear in logs, analytics payloads, URLs, screenshots, fixtures derived
from real people, or unsecured browser storage. Production handling MUST define retention,
correction, deletion, audit, and incident-response controls before accepting real candidate data.
The static prototype MUST use synthetic data only. Automated suggestions or match scores MUST be
explainable evidence for human review, never the sole basis for a consequential hiring decision.

### IV. Clear, Usable, and Human-Centred Workflows
Recruiters and candidates MUST always understand their current state, the next available action,
and the consequence of that action. Search, upload, autofill, consent, save, apply, shortlist,
compare, contact, and status-change flows MUST provide timely feedback and prevent or permit
recovery from mistakes. Candidate-facing language MUST not expose internal jargon; recruiter-facing
screens MUST distinguish self-reported facts, inferred signals, missing information, and private
notes. Common tasks MUST remain direct, while progressive disclosure MAY contain secondary detail.
Empty, loading, success, error, disabled, and no-results states MUST be deliberately designed and
tested. Usability decisions MUST prioritize comprehension and task completion over decorative
novelty.

### V. Maintainable Simplicity
Implementation MUST favor the smallest coherent solution that satisfies the documented workflow.
Repeated visual patterns, state transitions, validation rules, and data shapes MUST have a single
clear source of truth. Names MUST express recruiting-domain intent; modules and functions MUST keep
focused responsibilities; non-obvious privacy, accessibility, or scoring behavior MUST be
documented near its governing code or decision record. New dependencies, abstractions, and global
state MUST have a concrete, reviewed need. Dead code and contradictory style overrides MUST be
removed only when tests or explicit verification show that no supported behavior depends on them.

### VI. Evidence-Based Testing
Every behavior change MUST include verification proportional to its risk. Automated tests MUST
cover deterministic business rules, validation, data transformations, permission boundaries, and
regressions where practical. Integration or browser-level tests MUST cover critical candidate and
recruiter journeys, including keyboard operation and responsive states. Privacy controls,
candidate visibility, consent, sensitive-field access, and destructive actions require negative
tests as well as happy paths. Accessibility checks MUST combine automation with manual keyboard and
screen-reader-oriented review; visual and responsive changes MUST be inspected at representative
viewport sizes. A change MUST NOT be considered complete while relevant tests fail or required
manual evidence is absent.

### VII. Preserve Existing Functionality
Existing recruiter and candidate capabilities are contracts unless a specification explicitly
changes them. Before modifying a workflow, contributors MUST inventory its entry points, state,
data effects, accessibility semantics, responsive behavior, and downstream screens. Refactors and
visual redesigns MUST preserve those contracts and MUST add regression coverage for affected
critical paths. Intentional removals or behavioral changes require an approved specification,
migration or fallback treatment where stored data is affected, updated tests, and a clear release
note. Unrelated defects or cleanup MUST NOT be folded into a change without separate scope and
verification.

## Product and Data Constraints

- Recruiter access, candidate visibility, and private recruiter annotations MUST remain distinct
  authorization domains; UI hiding alone is not an authorization control.
- Resume upload and autofill MUST disclose what is extracted, let candidates review and correct
  values before publication, and never overwrite deliberate user edits without confirmation.
- Required fields MUST be justified by the minimum data needed for the immediate workflow.
  Optional fields MUST be identified as optional, and declining them MUST not silently block core
  tasks.
- Search and matching output MUST expose the evidence behind material signals, identify unknown or
  self-reported values, and support human correction. Protected traits and obvious proxies MUST
  not be used for ranking or filtering.
- Candidate sharing and export MUST use the least data required, communicate the audience, and
  respect the candidate's current visibility selection.
- The prototype's browser-local persistence is suitable only for synthetic demonstration data.
  Any production architecture MUST use authenticated, authorized, encrypted, auditable storage and
  transport with documented retention and deletion behavior.
- Performance budgets and browser support MUST be recorded before production release. Critical
  interaction feedback MUST not depend on slow or unavailable optional services.

## Delivery Workflow and Quality Gates

1. Each change MUST begin with a written user outcome, affected recruiter or candidate journey,
   acceptance criteria, and an explicit list of existing behaviors that must remain intact.
2. Design review MUST address accessibility, responsive behavior, privacy exposure, state and error
   handling, content clarity, and consistency with established patterns before implementation.
3. Implementation MUST keep data boundaries explicit, use synthetic fixtures, and avoid unrelated
   restructuring. Any justified exception to a principle MUST be documented in the change record.
4. Review MUST include automated results plus manual evidence appropriate to the change. Critical
   paths include recruiter sign-in and search, criteria review, results and comparison, candidate
   profile and notes, resume upload/autofill, consent and visibility, application, and status
   feedback.
5. Before release, reviewers MUST verify supported viewport behavior, keyboard navigation, focus and
   error handling, candidate-data exposure, and regression coverage. Known high-severity
   accessibility, privacy, data-loss, or critical-flow defects block release.
6. After release, discovered regressions MUST be recorded with a reproduction and protected by a
   regression test when feasible. Production candidate-data incidents MUST follow the documented
   response and notification process.

## Governance

This constitution is the highest project-level authority for product, design, implementation, and
review decisions. Feature specifications, plans, task lists, code reviews, and release decisions
MUST demonstrate compliance. Where two rules conflict, the interpretation that better protects
candidate rights, accessibility, and safe completion of core tasks takes precedence.

Amendments require a written proposal describing the motivation, affected principles and
workflows, compatibility impact, and any migration work. Adoption requires explicit approval from
the project owner or designated maintainers. The amendment MUST update this document's version and
date and MUST identify follow-up changes needed in active specifications or implementation.

Versions follow semantic versioning: MAJOR for removal or incompatible redefinition of governance;
MINOR for a new principle or materially expanded obligation; PATCH for clarification that does not
change required behavior. Every feature review MUST include a constitution check, and maintainers
MUST audit the constitution and representative recruiter and candidate journeys before each
production release or at least quarterly, whichever is more frequent. Exceptions MUST identify an
owner, rationale, bounded scope, risk controls, and expiry date; silent or permanent exceptions are
not permitted.

**Version**: 1.0.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-09-28
