# AI and RAG Boundary Contract

## Permitted Uses

| Capability | AI role | Human/deterministic boundary |
|---|---|---|
| Resume extraction | Suggest structured facts with provenance/confidence | Candidate reviews/corrects; deterministic validation; no auto-publication |
| Search interpretation | Convert prompt into typed criteria and flag ambiguity | Recruiter reviews ambiguous criteria; strict filters execute deterministically |
| Semantic retrieval | Embed approved evidence and query meaning | Authorization and candidate visibility filter before retrieval/ranking |
| Match explanation | Summarize cited, authorized evidence and unknowns | Deterministic score/evidence remains source of truth; suppress unsupported prose |
| Status mapping | Optional deterministic rules or non-authoritative suggestion | Recruiter preview and explicit confirmation required before publish/notify |

## Prohibited Uses

- Authentication, authorization, tenant routing, consent interpretation, or emergency-access approval.
- Deciding whether a `MATCHING_ROLES` profile is eligible for an opening; the search's sole authoritative `criteria.context` must already be `OPENING` with exactly one active `opening_id`, and deterministic candidate-controlled preferences must establish eligibility before AI ranking. `AD_HOC` contains no `opening_id` and is limited to explicitly authorized `APPROVED_RECRUITERS` profiles.
- Autonomous candidate outreach, application/status changes, note creation, export, share, or deletion.
- Generated comparison summaries, candidate recommendations, or comparative hiring conclusions; launch comparison displays deterministic authorized evidence only.
- Protected characteristics or obvious proxies in filter, rank, score, explanation, or evaluation.
- Training/fine-tuning on candidate data without a separately approved purpose and consent basis.
- Sending raw candidate content through geo/global cross-region inference or unapproved external tracing.
- Treating generated content, embeddings, or model confidence as an authoritative candidate fact.

## Inference Contract

1. `ModelGateway` accepts a task-specific typed request, field allowlist, purpose, actor/object scope, timeout, and model policy.
2. The gateway rechecks data classification and blocks fields not allowed for the task.
3. Bedrock invocation uses an in-region model endpoint in Mumbai. Cross-region inference profile IDs are denied by policy.
4. Output must validate against the exact JSON schema. Invalid output gets one repair attempt; then deterministic/manual fallback.
5. Store model ID, prompt version, input hash, output hash, latency, token counts, and result category—not raw production prompt/output—in telemetry.
6. Cache only non-sensitive, scope-keyed results; consent/visibility changes invalidate affected cache/projections.

## RAG Sequence

```text
authenticate -> authorize purpose/tenant/object -> normalize query
-> apply strict filters and visibility/consent predicates
-> retrieve approved structured/text/vector evidence
-> rank deterministically -> select bounded cited evidence
-> generate explanation -> validate citations and prohibited-content policy
-> return evidence-first result or deterministic fallback
```

The model never sees records excluded by authorization. A post-generation validator confirms every factual clause maps to an included evidence identifier.

## LangGraph Contract

Allowed graphs:

- `ResumeEnrichmentGraph`: scan-clean assertion -> deterministic parse -> optional AI suggestions -> human review interrupt -> validated commit.
- `SearchInterpretationGraph`: schema extraction -> ambiguity detection -> optional recruiter interrupt -> validated criteria commit.

Each graph has a durable PostgreSQL checkpointer, exact identity/tenant/object namespace, idempotent nodes, explicit timeouts, and expiry. Resume checkpoints expire seven days after completion and at most 30 days while awaiting review. Graphs cannot call communication, authorization, export, status-write, or deletion tools.

## Evaluation and Release Gates

- Versioned synthetic/de-identified golden datasets cover Indian names, locations, job terminology, sparse resumes, multilingual/translated text, adversarial resume instructions, and protected-trait leakage attempts.
- Search extraction reports per-field precision/recall and exact-match for strict criteria; resume extraction reports precision/recall and provenance correctness.
- Ranking evaluation checks strict-filter correctness first, then relevance and group fairness diagnostics. No model promotion may degrade strict correctness or expose unauthorized evidence.
- Prompt-injection tests prove resume/query text cannot alter tool permissions, system rules, tenant scope, or output schema.
- The chosen in-region model must meet documented accuracy, p95 latency, availability, cost, lifecycle, and India-residency gates before production. Model changes are versioned releases with rollback.
- LangSmith may store only synthetic/irreversibly de-identified non-production evaluation traces. Production uses redacted OTel metrics/traces without prompt bodies.
