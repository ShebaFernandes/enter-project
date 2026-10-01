import { useEffect, useRef, useState } from "react";
import type { PageProps } from "./mount";
import {
  Alert,
  Button,
  Card,
  Chip,
  Loading,
  StatusMessage,
} from "./components";
import { ApiError, responseJson } from "../shared/api-client";
import type { CandidateFinding } from "../recruiter/candidate-findings";

export type EvidenceItem = {
  label?: string;
  field?: string;
  provenance?: string;
};
export type SearchItem = {
  candidate_id: string;
  summary: Record<string, unknown>;
  evidence: EvidenceItem[];
  findings: CandidateFinding[];
  unknowns: string[];
  score?: string;
};
type Detail = {
  candidate_id: string;
  permitted_fields: Record<string, unknown>;
  evidence: EvidenceItem[];
  findings: CandidateFinding[];
  unknowns: string[];
};
const labels: Record<string, string> = {
  current_role: "Current role",
  current_company: "Current company",
  headline: "Headline",
  location: "Location",
  experience_years: "Experience (years)",
  skills: "Skills",
  work_arrangements: "Work arrangements",
  availability_date: "Availability",
};
export function fieldText(value: unknown): string {
  if (value === null || value === undefined || value === "" || value === "None")
    return "Unknown";
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  )
    return String(value);
  if (Array.isArray(value))
    return value.length ? value.map(fieldText).join(", ") : "None recorded";
  if (typeof value === "object" && "display" in value)
    return fieldText(value.display);
  return "Unavailable";
}
export function Finding({ finding }: { finding: CandidateFinding }) {
  const evidence = finding.evidence;
  return (
    <section
      className="result-finding"
      aria-label="Informational employment finding"
    >
      <Chip tone="unknown">Employment information · informational only</Chip>
      <p>{finding.message}</p>
      <p className="ui-help">
        This information does not change eligibility, score, rank or hiring
        status.
      </p>
      <details>
        <summary>Supporting evidence</summary>
        <dl>
          <dt>Company</dt>
          <dd>{fieldText(evidence.company)}</dd>
          <dt>Confirmed dates</dt>
          <dd>
            {evidence.confirmed_start_date} to {evidence.confirmed_end_date}
          </dd>
          <dt>Calculated duration</dt>
          <dd>
            {evidence.calculated_duration.calendar_months} months,{" "}
            {evidence.calculated_duration.remaining_days} days
          </dd>
          <dt>Calculation version</dt>
          <dd>{evidence.calculation_version}</dd>
          <dt>Evaluated</dt>
          <dd>{evidence.evaluated_at}</dd>
        </dl>
      </details>
    </section>
  );
}
export function Evidence({ items }: { items: EvidenceItem[] }) {
  return (
    <section>
      <h3>Matching evidence</h3>
      {items.length ? (
        <ul>
          {items.map((item, index) => (
            <li key={index}>
              {(item.label ?? item.field ?? "Evidence").replaceAll("_", " ")} ·{" "}
              {item.provenance === "CANDIDATE_REPORTED"
                ? "Candidate reported"
                : "Provenance unavailable"}
            </li>
          ))}
        </ul>
      ) : (
        <p>No matching evidence returned.</p>
      )}
    </section>
  );
}
export function EmploymentTimeline() {
  // The approved detail API supplies no full employment chronology. Do not infer
  // one from a finding or fetch wider candidate data using a different purpose.
  return (
    <section>
      <h3>Employment timeline</h3>
      <p>
        <Chip tone="unknown">Unavailable</Chip> Full employment history is not
        disclosed by this view.
      </p>
    </section>
  );
}
export function CandidateDetail({
  tenantId,
  candidateId,
  searchId,
  request,
  onUnavailable,
}: {
  tenantId: string;
  candidateId: string;
  searchId: string;
  request: PageProps["request"];
  onUnavailable?: () => void;
}) {
  const unavailable = useRef(onUnavailable);
  unavailable.current = onUnavailable;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    setDetail(null);
    setLoading(true);
    setError(false);
    void request(
      `/api/v1/tenants/${tenantId}/candidates/${candidateId}?search_id=${encodeURIComponent(searchId)}`,
      { signal: abort.signal },
    )
      .then(responseJson<Detail>)
      .then(({ data }) => {
        if (!abort.signal.aborted) setDetail(data);
      })
      .catch((failure: unknown) => {
        if (!abort.signal.aborted) {
          setError(true);
          if (
            failure instanceof ApiError &&
            [401, 403, 404, 410].includes(failure.status)
          )
            unavailable.current?.();
        }
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [tenantId, candidateId, searchId, request, attempt]);
  if (loading)
    return <Loading label="Loading current authorized candidate details…" />;
  if (error || !detail)
    return (
      <Alert>
        Candidate details are unavailable. Current access may have changed.
        <Button onClick={() => setAttempt((value) => value + 1)}>
          Retry authorized details
        </Button>
      </Alert>
    );
  return (
    <div className="ui-stack">
      <StatusMessage>
        Current authorized candidate details loaded.
      </StatusMessage>
      <Card title={fieldText(detail.permitted_fields.name)}>
        <dl className="detail-fields">
          {Object.entries(labels).map(([field, label]) => (
            <div key={field}>
              <dt>{label}</dt>
              <dd>
                {Object.hasOwn(detail.permitted_fields, field)
                  ? fieldText(detail.permitted_fields[field])
                  : "Unavailable"}
              </dd>
            </div>
          ))}
        </dl>
      </Card>
      <Evidence items={detail.evidence} />
      <EmploymentTimeline />
      {detail.findings.map((finding, index) => (
        <Finding key={index} finding={finding} />
      ))}
      {detail.unknowns.length > 0 && (
        <p>
          Unknown fields:{" "}
          {detail.unknowns
            .map((field) => field.replaceAll("_", " "))
            .join(", ")}
        </p>
      )}
      <a
        href={`/tenants/${tenantId}/recruiter/candidates/${candidateId}/?search_id=${encodeURIComponent(searchId)}`}
      >
        Manage this candidate
      </a>
      <p className="ui-help">
        Notes, shortlist, status and disclosure remain in the verified legacy
        workspace.
      </p>
    </div>
  );
}
