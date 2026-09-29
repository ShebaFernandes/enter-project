# Read-only mockup inventory

Source: `enter_recruiter_recruiter_candidate_ux.html`. This file is a preservation baseline and is not an application runtime dependency.

## Entry points and screens

| Screen | Entry/handoff | Principal controls and states |
|---|---|---|
| Recruiter sign-in | Initial screen | Work-email input, recruiter submit, candidate-platform handoff, inline error |
| Candidate platform | Candidate button/top navigation | Resume upload, profile fields, visibility/work-mode choices, consent, completeness, missing-fields dialog, public-profile preview |
| Recruiter search | Successful mock sign-in/top navigation | Prompt, suggested prompts, speech control/status, projects/recents side panel |
| Criteria review | Search submission | Requirement, preference, exclusion chips; `ANY`/`ALL`; add/edit/remove; run search |
| Results | Search execution | Filters, cards/table, status controls, candidate profile dialog, shortlist/compare controls |
| Public profile/application | Candidate handoff | Public summary, basic application fields, resume upload |
| Administration | Navigation/runtime rendering | Company, opening, job-search, and candidate-state mock administration |

## Client state and behavior

- Screens are mutually selected through `.screen.active`; no URL routing exists.
- Local storage holds companies, job openings/searches, candidate statuses, viewed profiles, recruiter notes, and Not relevant feedback. It is mock-only and must not become production storage.
- Synthetic candidate fixtures drive results, timelines, evidence, links, and comparison behavior.
- Speech uses progressive browser speech recognition; typed search remains available and speech never auto-submits.
- Profile and comparison overlays, filter panels, missing-field dialogs, and side panels are rendered dynamically.
- The layout switches at `860px`, with further component-specific compact rules. The production target remains 320 CSS pixels through desktop and 200% zoom.

## Preservation rules

Production work must preserve recognizable entry points, information hierarchy, search-review-results handoff, candidate profile structure, and responsive intent. Security, privacy, accessibility, validation, and server-authoritative behavior may require different implementation details. The source mockup remains unchanged for visual and regression comparison.
