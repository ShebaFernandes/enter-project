import { useEffect, useRef, useState } from "react";
import type { PageProps } from "./mount";
import {
  Alert,
  AppShell,
  Button,
  Card,
  Chip,
  EmptyState,
  Loading,
  StatusMessage,
} from "./components";
import { ApiError, responseJson } from "../shared/api-client";
import { handoffToken } from "../shared/workflow-handoff";
import { visualAssets } from "./visual-assets";

type ComparisonField = {
  state: "KNOWN" | "UNKNOWN" | "UNAVAILABLE";
  value: unknown;
  provenance: string[];
};
type Finding = {
  code: string;
  informational_only: boolean;
  message: string;
};
type Candidate = {
  candidate_id: string;
  permitted_fields: Record<string, ComparisonField>;
  findings: Finding[];
  unknowns: string[];
};
type ComparisonResult = { fields: string[]; candidates: Candidate[] };
type Selection = {
  search_id: string;
  candidate_ids: string[];
  etag: string;
};

const labels: Record<string, string> = {
  name: "Name",
  current_role: "Current role",
  current_company: "Current company",
  location: "Location",
  experience: "Experience",
  notice_or_availability: "Notice or availability",
  compensation_availability: "Compensation availability",
  skills: "Skills",
  employment: "Employment",
  education: "Education",
  preferences: "Preferences",
  match_evidence: "Why this match",
  informational_findings: "Informational findings",
};
function nameOf(candidate: Candidate) {
  const field = candidate.permitted_fields.name;
  return field?.state === "KNOWN" && typeof field.value === "string"
    ? field.value
    : "Candidate";
}
function values(value: unknown): string[] {
  if (value === null || value === undefined || value === "") return [];
  if (Array.isArray(value)) return value.flatMap(values);
  if (typeof value !== "object") return [String(value)];
  const record = value as Record<string, unknown>;
  if ("company" in record) {
    const role = String(record.role_title || "Role unknown");
    const company = String(record.company || "Company unknown");
    const start = String(record.start_date || "Start unknown");
    const end = record.is_current
      ? "Current"
      : String(record.end_date || "End unknown");
    return [`${role} — ${company} (${start} to ${end})`];
  }
  if ("school" in record) {
    return [
      [record.school, record.degree, record.field_of_study]
        .filter(Boolean)
        .map(String)
        .join(" · "),
    ];
  }
  if ("display" in record) return [String(record.display || "Unknown")];
  return ["Available as structured evidence"];
}
export function EvidenceValue({ field }: { field?: ComparisonField }) {
  if (!field || field.state === "UNAVAILABLE")
    return <Chip tone="unknown">Unavailable</Chip>;
  if (field.state === "UNKNOWN") return <Chip tone="unknown">Unknown</Chip>;
  const display = values(field.value);
  return (
    <div className="comparison-value">
      {display.length > 1 ? (
        <ul>
          {display.map((value, index) => (
            <li key={index}>{value}</li>
          ))}
        </ul>
      ) : (
        <p>{display[0] ?? "None recorded"}</p>
      )}
      {field.provenance.length > 0 && (
        <p className="ui-help">
          Evidence:{" "}
          {field.provenance.join(", ").replaceAll("_", " ").toLowerCase()}
        </p>
      )}
    </div>
  );
}
export function SelectionSummary({ count }: { count: number }) {
  return (
    <Card title="Current comparison">
      <p>{count} candidate columns in this view.</p>
      <p className="ui-help">
        Access, consent and field visibility were checked again for this view.
      </p>
    </Card>
  );
}
function CandidateCard({
  candidate,
  fields,
  remove,
  busy,
}: {
  candidate: Candidate;
  fields: string[];
  remove: () => void;
  busy: boolean;
}) {
  const name = nameOf(candidate);
  return (
    <article
      className="comparison-card"
      data-candidate-id={candidate.candidate_id}
    >
      <header className="comparison-card-head">
        <div className="comparison-avatar" aria-hidden="true">
          {name
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part[0])
            .join("")
            .toUpperCase()}
        </div>
        <div>
          <h2>{name}</h2>
          <p className="ui-help">Current authorized evidence</p>
        </div>
      </header>
      <Button
        variant="secondary"
        busy={busy}
        data-remove-candidate={candidate.candidate_id}
        onClick={remove}
      >
        Remove {name}
      </Button>
      <dl className="comparison-fields">
        {fields.map((field) => (
          <div key={field}>
            <dt>{labels[field] ?? field.replaceAll("_", " ")}</dt>
            <dd>
              <EvidenceValue field={candidate.permitted_fields[field]} />
            </dd>
          </div>
        ))}
      </dl>
      {candidate.findings.map((finding, index) => (
        <section
          key={`${finding.code}-${index}`}
          className="comparison-finding"
          aria-label="Informational employment finding"
        >
          <Chip tone="unknown">{finding.code}</Chip>
          <p>{finding.message}</p>
          <p className="ui-help">
            {finding.code} is informational only and does not affect ordering or
            scores.
          </p>
        </section>
      ))}
    </article>
  );
}
export function ComparisonGrid({
  result,
  remove,
  busy,
}: {
  result: ComparisonResult;
  remove: (candidate: Candidate) => void;
  busy: boolean;
}) {
  return (
    <section aria-labelledby="comparison-evidence-heading" className="ui-stack">
      <div>
        <h2 id="comparison-evidence-heading">Side-by-side evidence</h2>
        <p>
          Unknown and unavailable values remain explicit. This view provides no
          recommendation or automated hiring conclusion.
        </p>
      </div>
      <div className="comparison-grid">
        {result.candidates.map((candidate) => (
          <CandidateCard
            key={candidate.candidate_id}
            candidate={candidate}
            fields={result.fields}
            remove={() => remove(candidate)}
            busy={busy}
          />
        ))}
      </div>
    </section>
  );
}

export function CandidateComparison({ bootstrap, request }: PageProps) {
  const tenant = bootstrap.tenantId ?? "";
  const [token] = useState(handoffToken);
  const base = `/api/v1/tenants/${tenant}`;
  const [selection, setSelection] = useState<Selection | null>(null);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const focusAfterRemoval = useRef<number | null>(null);
  const comparisonKey = useRef(crypto.randomUUID());
  const returnKey = useRef(crypto.randomUUID());

  const clear = () => {
    generation.current++;
    setSelection(null);
    setResult(null);
    setMessage("");
  };
  useEffect(() => {
    const abort = new AbortController();
    const current = ++generation.current;
    setLoading(true);
    setError("");
    setMessage("");
    setSelection(null);
    setResult(null);
    void (async () => {
      if (!token) return;
      const { data: restored } = await responseJson<Selection>(
        await request(`${base}/search-handoffs/comparison-selection`, {
          signal: abort.signal,
          headers: { "X-Workflow-Handoff": token },
        }),
      );
      if (restored.candidate_ids.length < 2) return;
      const { data: compared } = await responseJson<ComparisonResult>(
        await request(`${base}/comparisons`, {
          signal: abort.signal,
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": comparisonKey.current,
          },
          body: JSON.stringify({
            candidate_ids: restored.candidate_ids,
            context_type: "SEARCH",
            context_id: restored.search_id,
          }),
        }),
      );
      if (current !== generation.current) return;
      const allowed = new Set(
        compared.candidates.map((item) => item.candidate_id),
      );
      const retained = restored.candidate_ids.filter((id) => allowed.has(id));
      let currentSelection = restored;
      if (retained.length !== restored.candidate_ids.length) {
        const { data: updated } = await responseJson<Selection>(
          await request(`${base}/search-handoffs/comparison-selection`, {
            signal: abort.signal,
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
              "X-Workflow-Handoff": token,
              "If-Match": restored.etag,
            },
            body: JSON.stringify({ candidate_ids: retained }),
          }),
        );
        currentSelection = updated;
      }
      if (current !== generation.current) return;
      setSelection(currentSelection);
      setResult(compared);
      const removed = restored.candidate_ids.length - retained.length;
      setMessage(
        removed
          ? `${removed} selected candidate${removed === 1 ? " is" : "s are"} no longer available. The comparison was updated.`
          : `${compared.candidates.length} currently authorized candidates loaded.`,
      );
    })()
      .catch((failure: unknown) => {
        if (abort.signal.aborted || current !== generation.current) return;
        setSelection(null);
        setResult(null);
        setMessage("");
        setError(
          failure instanceof ApiError && failure.status === 429
            ? "Too many requests. Wait before retrying current access."
            : "Comparison is unavailable. Current access may have changed; no saved candidate information is shown.",
        );
      })
      .finally(() => {
        if (!abort.signal.aborted && current === generation.current)
          setLoading(false);
      });
    return () => abort.abort();
  }, [attempt, base, request, token]);

  useEffect(() => {
    const visibility = () => {
      if (document.hidden) clear();
      else setAttempt((value) => value + 1);
    };
    document.addEventListener("visibilitychange", visibility);
    return () => document.removeEventListener("visibilitychange", visibility);
  }, []);

  useEffect(() => {
    if (busy || focusAfterRemoval.current === null) return;
    const remaining = Array.from(
      document.querySelectorAll<HTMLButtonElement>("[data-remove-candidate]"),
    );
    const index = focusAfterRemoval.current;
    focusAfterRemoval.current = null;
    (
      remaining[index] ??
      remaining[index - 1] ??
      document.getElementById("main")
    )?.focus();
  }, [busy, result]);

  async function remove(candidate: Candidate) {
    if (!selection || !token || busy) return;
    const controls = Array.from(
      document.querySelectorAll<HTMLButtonElement>("[data-remove-candidate]"),
    );
    const index = controls.findIndex(
      (item) => item.dataset.removeCandidate === candidate.candidate_id,
    );
    const ids = selection.candidate_ids.filter(
      (id) => id !== candidate.candidate_id,
    );
    setBusy(true);
    setError("");
    try {
      const { data: updated } = await responseJson<Selection>(
        await request(`${base}/search-handoffs/comparison-selection`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-Workflow-Handoff": token,
            "If-Match": selection.etag,
          },
          body: JSON.stringify({ candidate_ids: ids }),
        }),
      );
      setSelection(updated);
      setResult((current) =>
        current
          ? {
              ...current,
              candidates: current.candidates.filter(
                (item) => item.candidate_id !== candidate.candidate_id,
              ),
            }
          : null,
      );
      focusAfterRemoval.current = index;
      setMessage(
        `${ids.length} candidate${ids.length === 1 ? " remains" : "s remain"} selected.`,
      );
    } catch {
      setError(
        "Selection changed or is unavailable. Refresh before trying again; nothing was overwritten.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function returnToResults() {
    if (!token || busy) return;
    setBusy(true);
    try {
      const { data } = await responseJson<{ return_path: string }>(
        await request(`${base}/search-handoffs/comparison-selection/return`, {
          method: "POST",
          headers: {
            "X-Workflow-Handoff": token,
            "Idempotency-Key": returnKey.current,
          },
        }),
      );
      if (!data.return_path.startsWith(`/tenants/${tenant}/recruiter/search/`))
        throw new Error("Unexpected return path");
      location.assign(data.return_path);
    } catch {
      location.assign(`/tenants/${tenant}/recruiter/search/`);
    }
  }

  return (
    <div className="candidate-comparison-page">
      <AppShell
        title="Compare candidates"
        navigation={
          <Button
            variant="secondary"
            busy={busy}
            onClick={() => void returnToResults()}
          >
            Return to results
          </Button>
        }
      >
        {loading && <Loading label="Rechecking current candidate access…" />}
        {error && (
          <Alert>
            {error}
            <Button
              variant="secondary"
              onClick={() => setAttempt((value) => value + 1)}
            >
              Retry current access
            </Button>
          </Alert>
        )}
        {message && <StatusMessage>{message}</StatusMessage>}
        {!loading && !error && (!token || !selection || !result) && (
          <EmptyState
            title="No candidates selected"
            illustration={{
              src: visualAssets.candidateComparisonEmpty,
              width: 1024,
              height: 1024,
            }}
          >
            Select between two and ten candidates from the current authorized
            result view.
          </EmptyState>
        )}
        {result && (
          <>
            <SelectionSummary count={result.candidates.length} />
            <ComparisonGrid
              result={result}
              remove={(candidate) => void remove(candidate)}
              busy={busy}
            />
          </>
        )}
      </AppShell>
    </div>
  );
}
