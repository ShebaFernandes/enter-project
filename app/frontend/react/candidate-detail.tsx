import { useEffect, useRef, useState } from "react";
import type { PageProps } from "./mount";
import {
  Alert,
  Button,
  Card,
  Textarea,
  Select,
  Field,
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
type Work = {
  id: string;
  version: number;
  etag?: string;
  internal_status: string;
  shortlisted: boolean;
};
type Note = { id: string; body: string; created_at: string };
type Detail = {
  candidate_work?: Work;
  resume_download_available?: boolean;
  candidate_id: string;
  permitted_fields: Record<string, unknown>;
  evidence: EvidenceItem[];
  findings: CandidateFinding[];
  unknowns: string[];
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
  initialStatus,
  onWorkUpdated,
}: {
  initialStatus?: string;
  onWorkUpdated?: (status: string) => void;
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
  const [tab, setTab] = useState(initialStatus ? "Action" : "Overview");
  const [notes, setNotes] = useState<Note[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [status, setStatus] = useState("SOURCED");
  const [reason, setReason] = useState("");
  const [notesFailed, setNotesFailed] = useState(false);
  const [notesLoading, setNotesLoading] = useState(false);
  useEffect(() => {
    if (tab !== "Notes" || !detail?.candidate_work) return;
    const abort = new AbortController();
    setNotesLoading(true);
    setNotesFailed(false);
    void request(
      `/api/v1/tenants/${tenantId}/candidate-work/${detail.candidate_work.id}/notes`,
      { signal: abort.signal },
    )
      .then(responseJson<Note[]>)
      .then(({ data }) => {
        if (!abort.signal.aborted) setNotes(data);
      })
      .catch(() => {
        if (!abort.signal.aborted) setNotesFailed(true);
      })
      .finally(() => {
        if (!abort.signal.aborted) setNotesLoading(false);
      });
    return () => abort.abort();
  }, [tab, detail?.candidate_work?.id, request, tenantId]);
  async function addNote() {
    if (!detail?.candidate_work || !note.trim() || busy) return;
    setBusy(true);
    setFeedback("");
    try {
      const { data } = await responseJson<Note>(
        await request(
          `/api/v1/tenants/${tenantId}/candidate-work/${detail.candidate_work.id}/notes`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": crypto.randomUUID(),
            },
            body: JSON.stringify({
              body: note.trim(),
              hiring_team_visible: false,
            }),
          },
        ),
      );
      setNotes((current) => [...current, data]);
      setNote("");
      setFeedback("Note saved.");
    } catch {
      setFeedback("The note could not be saved. Your text is still here.");
    } finally {
      setBusy(false);
    }
  }
  async function updateWork(shortlisted?: boolean) {
    const work = detail?.candidate_work;
    if (!work || !work.etag || busy) return;
    setBusy(true);
    setFeedback("");
    try {
      const { data, etag } = await responseJson<Work>(
        await request(`/api/v1/tenants/${tenantId}/candidate-work/${work.id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "If-Match": work.etag,
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify(
            shortlisted === undefined
              ? {
                  internal_status: status,
                  structured_reasons: reason.trim() ? [reason.trim()] : [],
                  explanatory_note: reason.trim(),
                }
              : { shortlisted },
          ),
        }),
      );
      setDetail((current) =>
        current
          ? { ...current, candidate_work: { ...data, etag: etag ?? undefined } }
          : current,
      );
      onWorkUpdated?.(data.internal_status);
      setFeedback("Candidate status saved.");
    } catch {
      setFeedback(
        "Status could not be saved. Check your reason or reopen this profile to refresh its latest status.",
      );
    } finally {
      setBusy(false);
    }
  }
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
        if (!abort.signal.aborted) {
          setDetail(data);
          setStatus(
            initialStatus ?? data.candidate_work?.internal_status ?? "SOURCED",
          );
        }
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
  }, [tenantId, candidateId, searchId, request, attempt, initialStatus]);
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
  const fields = detail.permitted_fields;
  const name = fieldText(fields.name);
  const skills = Array.isArray(fields.skills) ? fields.skills : [];
  const history = Array.isArray(fields.employment_history)
    ? (fields.employment_history as Record<string, unknown>[])
    : [];
  const workspace = `/tenants/${tenantId}/recruiter/candidates/${candidateId}/?search_id=${encodeURIComponent(searchId)}`;
  return (
    <div className="candidate-profile-modal">
      <header className="profile-modal-heading">
        <div className="candidate-avatar">
          {name
            .split(/\s+/)
            .slice(0, 2)
            .map((x) => x[0])
            .join("")}
        </div>
        <div>
          <h2>{name}</h2>
          <p>
            {fieldText(fields.current_role)}
            {fields.current_company
              ? ` at ${fieldText(fields.current_company)}`
              : ""}
          </p>
          <div className="modal-resume-actions">
            <a className="ui-button" href={workspace}>
              Send resume
            </a>
            {detail.resume_download_available ? (
              <a
                className="ui-button"
                href={`/api/v1/tenants/${tenantId}/candidates/${candidateId}?search_id=${encodeURIComponent(searchId)}&download=resume`}
              >
                Download resume
              </a>
            ) : (
              <span className="ui-help">
                Resume download unavailable for this audience.
              </span>
            )}
          </div>
          <div className="modal-skills">
            {skills.map((skill, i) => (
              <Chip key={i} tone="sage">
                {fieldText(skill)}
              </Chip>
            ))}
          </div>
        </div>
      </header>
      <div className="profile-modal-facts">
        {[
          ["Location", fields.location],
          ["Experience", fields.experience_years],
          ["Notice period", fields.notice_period],
          ["Current salary", fields.current_salary],
        ].map(([label, value]) => (
          <div key={String(label)}>
            <span>{String(label)}</span>
            <strong>
              {fieldText(value)}
              {label === "Experience" && value != null ? " years" : ""}
            </strong>
          </div>
        ))}
      </div>
      <div
        className="profile-modal-tabs"
        aria-label="Candidate profile sections"
      >
        {["Overview", "Notes", "Action"].map((name) => (
          <Button
            key={name}
            variant={tab === name ? "primary" : "secondary"}
            aria-pressed={tab === name}
            onClick={() => {
              setTab(name);
              setFeedback("");
            }}
          >
            {name}
          </Button>
        ))}
      </div>
      {feedback && <StatusMessage>{feedback}</StatusMessage>}
      {tab === "Overview" && (
        <div className="profile-modal-overview">
          <Card title="Overview">
            <h3>Summary</h3>
            <p>
              {fields.headline
                ? fieldText(fields.headline)
                : "No summary has been added."}
            </p>
            <h3>Meaningful work</h3>
            <p>
              {fields.meaningful_work
                ? fieldText(fields.meaningful_work)
                : "Not provided by the candidate."}
            </p>
            <h3>Career history</h3>
            {history.length ? (
              <ol className="modal-career-list">
                {history.map((job, i) => (
                  <li key={i}>
                    <strong>{fieldText(job.company)}</strong>
                    <p>{fieldText(job.role_title)}</p>
                    <small>
                      {fieldText(job.start_date)} —{" "}
                      {job.is_current ? "Present" : fieldText(job.end_date)}
                    </small>
                  </li>
                ))}
              </ol>
            ) : (
              <p>No employment history is available in this view.</p>
            )}
          </Card>
          <Evidence items={detail.evidence} />
          {detail.findings.map((finding, i) => (
            <Finding key={i} finding={finding} />
          ))}
        </div>
      )}
      {tab === "Notes" && (
        <section className="modal-notes">
          <h3>Recruiter notes</h3>
          {!detail.candidate_work ? (
            <p>Notes are unavailable for this profile.</p>
          ) : (
            <>
              <p>Private to authorized recruiters in your company.</p>
              {notesLoading && <Loading label="Loading notes…" />}
              {notesFailed && (
                <Alert>
                  Notes could not be loaded. Reopen this tab to retry.
                </Alert>
              )}
              {!notesLoading && !notesFailed && !notes.length && (
                <p>No notes yet.</p>
              )}
              {notes.map((n) => (
                <article key={n.id}>
                  <p>{n.body}</p>
                  <small>{new Date(n.created_at).toLocaleString()}</small>
                </article>
              ))}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void addNote();
                }}
              >
                <Field label="Add a note">
                  {(p) => (
                    <Textarea
                      {...p}
                      value={note}
                      maxLength={5000}
                      disabled={busy}
                      onChange={(e) => setNote(e.target.value)}
                    />
                  )}
                </Field>
                <Button type="submit" busy={busy} disabled={!note.trim()}>
                  Save note
                </Button>
              </form>
            </>
          )}
        </section>
      )}
      {tab === "Action" && (
        <section className="modal-actions">
          <h3>Candidate actions</h3>
          {detail.candidate_work?.etag ? (
            <>
              <Button
                variant="secondary"
                busy={busy}
                onClick={() =>
                  void updateWork(!detail.candidate_work?.shortlisted)
                }
              >
                {detail.candidate_work.shortlisted
                  ? "Remove from shortlist"
                  : "Shortlist candidate"}
              </Button>
              <Field label="Recruiting status">
                {(p) => (
                  <Select
                    {...p}
                    value={status}
                    disabled={busy}
                    onChange={(e) => setStatus(e.target.value)}
                  >
                    {[
                      "SOURCED",
                      "SHORTLISTED",
                      "CONTACTED",
                      "SCREENING",
                      "INTERVIEWING",
                      "OFFERED",
                      "REJECTED",
                      "NOT_RELEVANT",
                      "HIRED",
                    ].map((value) => (
                      <option key={value} value={value}>
                        {value.toLowerCase().replaceAll("_", " ")}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Reason for status change">
                {(p) => (
                  <Textarea
                    {...p}
                    value={reason}
                    maxLength={200}
                    onChange={(e) => setReason(e.target.value)}
                  />
                )}
              </Field>
              <Button busy={busy} onClick={() => void updateWork()}>
                Save status
              </Button>
            </>
          ) : (
            <p>Status editing is currently unavailable.</p>
          )}
          <p>Resume sharing requires a destination and disclosure review.</p>
          <a className="ui-button" href={workspace}>
            Open resume sharing and candidate workspace
          </a>
        </section>
      )}
    </div>
  );
}
