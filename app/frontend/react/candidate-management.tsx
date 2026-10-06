import { useEffect, useRef, useState } from "react";
import type { PageProps } from "./mount";
import {
  Alert,
  AppShell,
  Button,
  Card,
  Checkbox,
  Chip,
  ConflictPanel,
  Dialog,
  Field,
  Loading,
  Select,
  Textarea,
  TextInput,
  WorkspaceNavigation,
} from "./components";
import {
  Evidence,
  Finding,
  fieldText,
  type EvidenceItem,
} from "./candidate-detail";
import type { CandidateFinding } from "../recruiter/candidate-findings";
import type { ConflictPayload } from "../shared/conflict-resolution";
import { ApiError, responseJson } from "../shared/api-client";
import {
  DeliveryFeedback,
  DisclosurePreview,
  InternalStatus,
  NotesPanel,
  PublicationPreview,
  ShortlistControl,
} from "./management-components";

type Work = {
  id: string;
  internal_status: string;
  shortlisted: boolean;
  structured_reasons: string[];
  explanatory_note: string | null;
};
type Detail = {
  permitted_fields: Record<string, unknown>;
  evidence: EvidenceItem[];
  findings: CandidateFinding[];
  unknowns: string[];
  candidate_work: Work;
  application_context?: {
    id: string;
    etag: string;
    internal_status: string;
    candidate_status: string;
  } | null;
};
type Note = { body: string; created_at: string };
type Disclosure = {
  preview_id: string;
  preview_hash: string;
  destination: { type: string; label: string };
  permitted_fields: string[];
  excluded_fields: string[];
  expires_at: string;
  state: string;
  result_category: string;
};
const statuses = [
  "SOURCED",
  "SHORTLISTED",
  "CONTACTED",
  "SCREENING",
  "INTERVIEWING",
  "OFFERED",
  "REJECTED",
  "NOT_RELEVANT",
  "HIRED",
];
const publicStatuses = [
  "APPLIED",
  "PROFILE_VIEWED",
  "SHORTLISTED",
  "RECRUITER_INTERESTED",
  "INTERVIEW_REQUESTED",
  "OFFER_MADE",
  "NOT_SELECTED",
  "WITHDRAWN",
];
const reasons = [
  "Wrong depth",
  "Wrong company context",
  "Skill not deep enough",
  "Wrong seniority",
  "Wrong location",
  "Not enough evidence",
];
const publicFields = [
  "name",
  "headline",
  "current_role",
  "current_company",
  "location",
  "experience_years",
  "skills",
  "email",
  "phone",
];
const label = (value: string) => value.replaceAll("_", " ").toLowerCase();

export function CandidateManagement({ bootstrap, request }: PageProps) {
  const tenant = bootstrap.tenantId,
    candidate = bootstrap.candidateId;
  const query = new URLSearchParams(location.search);
  const search = query.get("search_id") ?? "";
  const requestedAction = query.get("action");
  const base = `/api/v1/tenants/${tenant}`;
  const detailUrl = `${base}/candidates/${candidate}?search_id=${encodeURIComponent(search)}`;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [context, setContext] = useState<"CANDIDATE_WORK" | "APPLICATION">(
    "CANDIDATE_WORK",
  );
  const [work, setWork] = useState<Work | null>(null);
  const [etag, setEtag] = useState("");
  const [notes, setNotes] = useState<Note[]>([]);
  const [note, setNote] = useState("");
  const [teamNote, setTeamNote] = useState(false);
  const [internal, setInternal] = useState("SOURCED");
  const [shortlist, setShortlist] = useState(false);
  const [selectedReasons, setReasons] = useState<string[]>([]);
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [confirmStatus, setConfirmStatus] = useState(false);
  const [conflict, setConflict] = useState<ConflictPayload | null>(null);
  const [publication, setPublication] = useState<{
    preview_id: string;
    suggested_candidate_status: string | null;
    etag: string;
  } | null>(null);
  const [publishedChoice, setPublishedChoice] = useState("PROFILE_VIEWED");
  const [purpose, setPurpose] = useState(
    requestedAction === "email" || requestedAction === "whatsapp"
      ? "CANDIDATE_CONTACT"
      : "HIRING_TEAM_SHARE",
  );
  const [destinationType, setDestinationType] = useState(
    requestedAction === "email"
      ? "CANDIDATE_EMAIL"
      : requestedAction === "whatsapp"
        ? "CANDIDATE_WHATSAPP"
        : "HIRING_TEAM",
  );
  const [destinationId, setDestinationId] = useState("");
  const [destinationLabel, setDestinationLabel] = useState("");
  const [fields, setFields] = useState<string[]>([]);
  const [preview, setPreview] = useState<Disclosure | null>(null);
  const generation = useRef(0);
  const keys = useRef(new Map<string, { body: string; key: string }>());
  useEffect(() => {
    if (detail && requestedAction)
      document.getElementById("disclosure")?.scrollIntoView({ block: "start" });
  }, [detail, requestedAction]);
  const clear = () => {
    generation.current++;
    setDetail(null);
    setWork(null);
    setNotes([]);
    setNote("");
    setTeamNote(false);
    setPreview(null);
    setPublication(null);
    setConflict(null);
    setExplanation("");
    setReasons([]);
    setConfirmStatus(false);
    setInternal("SOURCED");
    setShortlist(false);
    setEtag("");
    setDestinationId("");
    setDestinationLabel("");
    setFields([]);
    setMessage("");
    keys.current.clear();
  };
  const resetWork = (value: Work) => {
    setInternal(value.internal_status);
    setShortlist(value.shortlisted);
    setReasons(value.structured_reasons ?? []);
    setExplanation(value.explanatory_note ?? "");
  };
  const fail = (failure: unknown) => {
    if (failure instanceof DOMException && failure.name === "AbortError")
      return;
    if (failure instanceof ApiError && failure.status === 409) {
      setError(
        "Information changed. Review the conflict or reload current information before retrying.",
      );
      return;
    }
    if (failure instanceof ApiError && failure.status === 400) {
      setPreview(null);
      setPublication(null);
      setError(
        "Validation failed. Review the selected record, destination, fields and required feedback before submitting again.",
      );
      return;
    }
    if (
      failure instanceof ApiError &&
      [401, 403, 404, 410].includes(failure.status)
    ) {
      clear();
      setError(
        "Candidate information is unavailable. Current access may have changed. Return to search.",
      );
    } else
      setError(
        failure instanceof ApiError && failure.status === 429
          ? "Too many requests. Wait before trying again."
          : "Unable to complete this action. Check current information before retrying; no automatic retry was made.",
      );
  };
  useEffect(() => {
    const abort = new AbortController();
    const current = ++generation.current;
    setLoading(true);
    setError("");
    setDetail(null);
    setWork(null);
    void (async () => {
      if (!tenant || !candidate || !/^[a-f0-9-]{36}$/i.test(search))
        throw new ApiError(404, null);
      const { data: loaded } = await responseJson<Detail>(
        await request(detailUrl, { signal: abort.signal }),
      );
      const source = await responseJson<Work>(
        await request(`${base}/candidate-work/${loaded.candidate_work.id}`, {
          signal: abort.signal,
        }),
      );
      const app = loaded.application_context;
      if (context === "APPLICATION" && !app) throw new ApiError(404, null);
      const loadedWork =
        context === "APPLICATION" && app
          ? {
              id: app.id,
              internal_status: app.internal_status,
              shortlisted: false,
              structured_reasons: [],
              explanatory_note: null,
            }
          : source.data;
      const version = context === "APPLICATION" && app ? app.etag : source.etag;
      const { data: loadedNotes } = await responseJson<Note[]>(
        await request(
          `${base}/${context === "APPLICATION" ? "applications" : "candidate-work"}/${loadedWork.id}/notes`,
          { signal: abort.signal },
        ),
      );
      if (abort.signal.aborted || generation.current !== current) return;
      setDetail(loaded);
      setWork(loadedWork);
      setEtag(version ?? "");
      setNotes(loadedNotes);
      resetWork(loadedWork);
    })()
      .catch((failure) => {
        if (!abort.signal.aborted) fail(failure);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => {
      abort.abort();
      generation.current++;
    };
    // The route/bootstrap are immutable for a mounted page. Retry reloads fresh authorization.
  }, [request, detailUrl, base, tenant, candidate, search, attempt, context]);
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        clear();
        setAttempt((v) => v + 1);
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);
  const dirty = Boolean(
    note ||
      (work &&
        (internal !== work.internal_status ||
          shortlist !== work.shortlisted ||
          explanation !== (work.explanatory_note ?? "") ||
          JSON.stringify(selectedReasons) !==
            JSON.stringify(work.structured_reasons ?? []))),
  );
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    if (dirty) window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  async function action(task: () => Promise<void>) {
    if (busy) return;
    const current = generation.current;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      // Recheck the source SearchRun, current visibility/consent and object scope.
      // This does not substitute for the mutation endpoint's own authorization.
      const { data: fresh } = await responseJson<Detail>(
        await request(detailUrl),
      );
      if (current !== generation.current) return;
      setDetail((previous) =>
        previous
          ? {
              ...previous,
              permitted_fields: fresh.permitted_fields,
              evidence: fresh.evidence,
              findings: fresh.findings,
              unknowns: fresh.unknowns,
            }
          : null,
      );
      await task();
    } catch (failure) {
      if (current === generation.current) fail(failure);
    } finally {
      setBusy(false);
    }
  }
  async function mutate<T>(
    url: string,
    body: unknown,
    method = "POST",
    version?: string,
  ) {
    const current = generation.current;
    const encoded = JSON.stringify(body);
    const old = keys.current.get(url);
    const entry =
      old?.body === encoded ? old : { body: encoded, key: crypto.randomUUID() };
    keys.current.set(url, entry);
    const response = await request(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": entry.key,
        ...(version ? { "If-Match": version } : {}),
      },
      body: encoded,
    });
    if (current !== generation.current)
      throw new DOMException("Page context changed", "AbortError");
    if (response.status === 409) {
      const payload = (await response.json()) as Partial<ConflictPayload>;
      if (
        payload.current &&
        payload.attempted &&
        Array.isArray(payload.changed_fields) &&
        typeof payload.current_etag === "string" &&
        (url.endsWith("/internal-status") ||
          url === `${base}/candidate-work/${work?.id}`)
      )
        setConflict(payload as ConflictPayload);
      else
        setError(
          "Information changed. Reload current information before trying again.",
        );
      setPreview(null);
      setPublication(null);
      throw new ApiError(409, response.headers.get("ETag"));
    }
    const result = await responseJson<T>(response);
    if (current !== generation.current)
      throw new DOMException("Page context changed", "AbortError");
    keys.current.delete(url);
    return result;
  }
  const saveStatus = () =>
    void action(async () => {
      if (!work || !etag) throw new ApiError(409, null);
      const { data, etag: version } = await mutate<Work>(
        context === "APPLICATION"
          ? `${base}/applications/${work.id}/internal-status`
          : `${base}/candidate-work/${work.id}`,
        {
          internal_status: internal,
          ...(context === "CANDIDATE_WORK" ? { shortlisted: shortlist } : {}),
          structured_reasons: selectedReasons,
          explanatory_note: explanation || null,
        },
        context === "APPLICATION" ? "PUT" : "PATCH",
        etag,
      );
      const saved = {
        ...work,
        ...data,
        structured_reasons: selectedReasons,
        explanatory_note: explanation || null,
      };
      setWork(saved);
      resetWork(saved);
      if (context === "APPLICATION" && detail?.application_context)
        setDetail({
          ...detail,
          application_context: {
            ...detail.application_context,
            internal_status: data.internal_status,
            etag: version ?? "",
          },
        });
      setEtag(version ?? "");
      setConfirmStatus(false);
      setConflict(null);
      setMessage(
        "Internal status saved. Candidate-facing status was not published.",
      );
    });
  const cancelStatus = () => {
    if (work) resetWork(work);
    setConfirmStatus(false);
  };
  const invalidateDisclosure = () => {
    setPreview(null);
  };
  return (
    <AppShell
      title="Candidate workspace"
      navigation={
        <>
          <WorkspaceNavigation
            label="Recruiter workspace"
            items={[
              {
                label: "Return to search",
                href: `/tenants/${tenant}/recruiter/search/`,
              },
            ]}
          />
          <Button
            disabled={busy}
            variant="secondary"
            onClick={() => {
              if (
                dirty &&
                !window.confirm("Discard unsaved changes and sign out?")
              )
                return;
              setBusy(true);
              void request("/api/v1/session/sign-out", { method: "DELETE" })
                .then((response) => {
                  if (!response.ok) throw new ApiError(response.status, null);
                  clear();
                  location.replace("/");
                })
                .catch(() => setError("Sign-out failed. Try again."))
                .finally(() => setBusy(false));
            }}
          >
            Sign out
          </Button>
        </>
      }
    >
      {error && (
        <Alert>
          {error}
          <Button
            disabled={busy}
            variant="secondary"
            onClick={() => {
              clear();
              setAttempt((v) => v + 1);
            }}
          >
            Reload current information
          </Button>
        </Alert>
      )}
      <DeliveryFeedback>{message}</DeliveryFeedback>
      {loading ? (
        <Loading label="Loading current authorized candidate context…" />
      ) : !detail || !work ? (
        <Button onClick={() => setAttempt((v) => v + 1)}>
          Retry authorized candidate
        </Button>
      ) : (
        <>
          <nav className="ui-nav" aria-label="Candidate sections">
            <a href="#profile">Profile</a>
            <a href="#notes">Notes</a>
            <a href="#actions">Actions</a>
            <a href="#disclosure">Contact and share</a>
          </nav>
          {detail.application_context && (
            <Field
              label="Management record"
              help="Candidate work and the existing application are separate records. Discard or save drafts before switching."
            >
              {(props) => (
                <Select
                  {...props}
                  value={context}
                  disabled={busy || dirty}
                  onChange={(e) => {
                    clear();
                    setContext(
                      e.target.value as "CANDIDATE_WORK" | "APPLICATION",
                    );
                  }}
                >
                  <option value="CANDIDATE_WORK">Sourced candidate work</option>
                  <option value="APPLICATION">Existing application</option>
                </Select>
              )}
            </Field>
          )}
          <section id="profile" className="ui-stack">
            <Card title={fieldText(detail.permitted_fields.name)}>
              <dl className="detail-fields">
                {[
                  "headline",
                  "current_role",
                  "current_company",
                  "location",
                  "experience_years",
                  "skills",
                ].map((field) => (
                  <div key={field}>
                    <dt>{label(field)}</dt>
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
            {detail.findings.map((finding, i) => (
              <Finding key={i} finding={finding} />
            ))}
            {detail.unknowns.length > 0 && (
              <p>Unknown: {detail.unknowns.map(label).join(", ")}</p>
            )}
          </section>
          <section id="notes">
            <NotesPanel>
              <p>
                Notes belong only to the selected{" "}
                {context === "APPLICATION"
                  ? "existing application"
                  : "sourced candidate-work record"}
                . They are not visible to the candidate.
              </p>
              <Field label="Recruiter note">
                {(props) => (
                  <Textarea
                    {...props}
                    value={note}
                    maxLength={5000}
                    disabled={busy}
                    onChange={(e) => setNote(e.target.value)}
                  />
                )}
              </Field>
              <Checkbox
                label="Make this note visible to the authorized hiring team"
                checked={teamNote}
                disabled={busy}
                onChange={(e) => setTeamNote(e.target.checked)}
              />
              <div className="ui-row">
                <Button
                  busy={busy}
                  disabled={!note.trim()}
                  onClick={() =>
                    void action(async () => {
                      const current = generation.current;
                      const notesUrl = `${base}/${context === "APPLICATION" ? "applications" : "candidate-work"}/${work.id}/notes`;
                      await mutate(notesUrl, {
                        body: note,
                        hiring_team_visible: teamNote,
                      });
                      setNote("");
                      const { data } = await responseJson<Note[]>(
                        await request(notesUrl),
                      );
                      if (current !== generation.current) return;
                      setNotes(data);
                      setMessage(
                        "Note saved. It is not visible to the candidate.",
                      );
                    })
                  }
                >
                  Save note
                </Button>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={() => setNote("")}
                >
                  Discard note draft
                </Button>
              </div>
              {notes.length ? (
                <ul>
                  {notes.map((item, i) => (
                    <li key={i}>
                      <p>{item.body}</p>
                      <small>{item.created_at}</small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No notes recorded.</p>
              )}
            </NotesPanel>
          </section>
          <section id="actions">
            <InternalStatus>
              <p>
                CandidateWork and Application remain separate. These changes do
                not publish a candidate-facing status.
              </p>
              <Field label="Internal status">
                {(props) => (
                  <Select
                    {...props}
                    value={internal}
                    disabled={busy}
                    onChange={(e) => {
                      setInternal(e.target.value);
                      setPublication(null);
                    }}
                  >
                    {statuses.map((value) => (
                      <option key={value} value={value}>
                        {label(value)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              {context === "CANDIDATE_WORK" && (
                <ShortlistControl
                  checked={shortlist}
                  disabled={busy}
                  onChange={(e) => setShortlist(e.target.checked)}
                />
              )}
              {internal === "NOT_RELEVANT" && (
                <fieldset>
                  <legend>Not relevant feedback</legend>
                  {reasons.map((reason) => (
                    <Checkbox
                      key={reason}
                      label={reason}
                      checked={selectedReasons.includes(reason)}
                      disabled={busy}
                      onChange={(e) =>
                        setReasons(
                          e.target.checked
                            ? [...selectedReasons, reason]
                            : selectedReasons.filter((v) => v !== reason),
                        )
                      }
                    />
                  ))}
                </fieldset>
              )}
              <Field label="Internal explanation (optional)">
                {(props) => (
                  <Textarea
                    {...props}
                    value={explanation}
                    maxLength={2000}
                    disabled={busy}
                    onChange={(e) => setExplanation(e.target.value)}
                  />
                )}
              </Field>
              {context === "APPLICATION" && (
                <p className="ui-help">
                  Previous application feedback is unavailable in this read
                  view. Saving submits the feedback shown here as the new
                  internal feedback; no history is erased.
                </p>
              )}
              <div className="ui-row">
                <Button
                  busy={busy}
                  onClick={() =>
                    internal === "NOT_RELEVANT"
                      ? setConfirmStatus(true)
                      : saveStatus()
                  }
                >
                  Save internal status
                </Button>
                <Button
                  variant="secondary"
                  disabled={busy}
                  onClick={cancelStatus}
                >
                  Discard status changes
                </Button>
              </div>
              <p className="ui-help">
                Status changes are recorded in server-side history. The current
                API does not expose a history list.
              </p>
            </InternalStatus>
          </section>
          {conflict && (
            <ConflictPanel
              conflict={conflict}
              onDiscard={() => {
                setConflict(null);
                setAttempt((v) => v + 1);
              }}
              onReview={() => {
                setEtag(conflict.current_etag);
                setConflict(null);
                setMessage(
                  "Review your changes, then explicitly save against the current version.",
                );
              }}
              onResubmit={() => {
                setEtag(conflict.current_etag);
                setConflict(null);
                setMessage(
                  "Current version selected. Review and use Save internal status to resubmit.",
                );
              }}
            />
          )}
          <Dialog
            open={confirmStatus}
            onClose={cancelStatus}
            title="Confirm Not relevant feedback"
          >
            <p>
              This updates the selected record's internal status only. It does
              not publish a candidate-facing status.
            </p>
            <p>
              {selectedReasons.join(", ") || "No structured reason selected"}
            </p>
            <Button
              busy={busy}
              disabled={!selectedReasons.length && !explanation.trim()}
              onClick={saveStatus}
            >
              Confirm internal change
            </Button>
            <Button disabled={busy} onClick={cancelStatus}>
              Cancel
            </Button>
          </Dialog>
          <PublicationPreview>
            {detail.application_context ? (
              <>
                <p>
                  Existing application status:{" "}
                  <Chip>
                    {label(detail.application_context.candidate_status)}
                  </Chip>
                  . Publication is separate from candidate work.
                </p>
                <Button
                  busy={busy}
                  onClick={() =>
                    void action(async () => {
                      const app = detail.application_context!;
                      const { data, etag: version } = await mutate<{
                        preview_id: string;
                        suggested_candidate_status: string | null;
                      }>(
                        `${base}/applications/${app.id}/status-preview`,
                        { internal_status: app.internal_status },
                        "POST",
                        app.etag,
                      );
                      setPublication({ ...data, etag: version ?? "" });
                      if (context === "APPLICATION") setEtag(version ?? "");
                      setPublishedChoice(
                        data.suggested_candidate_status ?? app.candidate_status,
                      );
                      setDetail({
                        ...detail,
                        application_context: { ...app, etag: version ?? "" },
                      });
                    })
                  }
                >
                  Preview candidate-facing status
                </Button>
              </>
            ) : (
              <p>
                No linked application. No application is created and no
                candidate-facing status can be published here.
              </p>
            )}
          </PublicationPreview>
          <Dialog
            open={Boolean(publication)}
            onClose={() => setPublication(null)}
            title="Confirm candidate-facing publication"
          >
            <p>
              Review the candidate-visible status. Nothing is published until
              you confirm. No notification channel is selected.
            </p>
            <Field label="Candidate-facing status">
              {(props) => (
                <Select
                  {...props}
                  value={publishedChoice}
                  disabled={busy}
                  onChange={(e) => setPublishedChoice(e.target.value)}
                >
                  {publicStatuses.map((value) => (
                    <option key={value} value={value}>
                      {label(value)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Button
              busy={busy}
              onClick={() =>
                void action(async () => {
                  if (!publication || !detail.application_context) return;
                  await mutate(
                    `${base}/applications/${detail.application_context.id}/status-publish`,
                    {
                      preview_id: publication.preview_id,
                      candidate_status: publishedChoice,
                      confirm: true,
                      notify_channels: [],
                    },
                    "POST",
                    publication.etag,
                  );
                  setPublication(null);
                  setAttempt((v) => v + 1);
                  setMessage(
                    "Candidate-facing status published after confirmation.",
                  );
                })
              }
            >
              Confirm publication
            </Button>
            <Button disabled={busy} onClick={() => setPublication(null)}>
              Cancel publication
            </Button>
          </Dialog>
          <section id="disclosure">
            <DisclosurePreview>
              <p>
                Only the server-approved minimum fields may be disclosed.
                Preview the destination and fields before confirming.
              </p>
              <Field label="Disclosure purpose">
                {(props) => (
                  <Select
                    {...props}
                    value={purpose}
                    disabled={busy}
                    onChange={(e) => {
                      setPurpose(e.target.value);
                      invalidateDisclosure();
                    }}
                  >
                    <option value="HIRING_TEAM_SHARE">Hiring team share</option>
                    <option value="CANDIDATE_CONTACT">Candidate contact</option>
                  </Select>
                )}
              </Field>
              <Field label="Destination type">
                {(props) => (
                  <Select
                    {...props}
                    value={destinationType}
                    disabled={busy}
                    onChange={(e) => {
                      setDestinationType(e.target.value);
                      invalidateDisclosure();
                    }}
                  >
                    <option value="HIRING_TEAM">Hiring team</option>
                    <option value="CANDIDATE_EMAIL">Candidate email</option>
                    <option value="CANDIDATE_WHATSAPP">
                      Candidate WhatsApp (simulated)
                    </option>
                  </Select>
                )}
              </Field>
              <Field label="Destination identifier">
                {(props) => (
                  <TextInput
                    {...props}
                    value={destinationId}
                    disabled={busy}
                    onChange={(e) => {
                      setDestinationId(e.target.value);
                      invalidateDisclosure();
                    }}
                  />
                )}
              </Field>
              <Field label="Destination label">
                {(props) => (
                  <TextInput
                    {...props}
                    value={destinationLabel}
                    disabled={busy}
                    onChange={(e) => {
                      setDestinationLabel(e.target.value);
                      invalidateDisclosure();
                    }}
                  />
                )}
              </Field>
              <fieldset>
                <legend>Requested fields</legend>
                {publicFields.map((field) => (
                  <Checkbox
                    key={field}
                    label={label(field)}
                    checked={fields.includes(field)}
                    disabled={busy}
                    onChange={(e) => {
                      setFields(
                        e.target.checked
                          ? [...fields, field]
                          : fields.filter((v) => v !== field),
                      );
                      invalidateDisclosure();
                    }}
                  />
                ))}
              </fieldset>
              <Button
                busy={busy}
                disabled={
                  !fields.length ||
                  !destinationId.trim() ||
                  !destinationLabel.trim()
                }
                onClick={() =>
                  void action(async () => {
                    const { data } = await mutate<Disclosure>(
                      `${base}/candidates/${candidate}/disclosures/preview`,
                      {
                        context_type: context,
                        context_id: work.id,
                        purpose,
                        destination: {
                          type: destinationType,
                          identifier: destinationId,
                          label: destinationLabel,
                        },
                        requested_fields: fields,
                      },
                    );
                    setPreview(data);
                  })
                }
              >
                Preview disclosure
              </Button>
            </DisclosurePreview>
          </section>
          <Dialog
            open={Boolean(preview)}
            onClose={() => setPreview(null)}
            title="Confirm disclosure"
          >
            <p>Destination: {preview?.destination.label}</p>
            <p>
              Permitted fields:{" "}
              {preview?.permitted_fields.map(label).join(", ") || "None"}
            </p>
            <p>
              Excluded fields:{" "}
              {preview?.excluded_fields.map(label).join(", ") || "None"}
            </p>
            <p>
              Consent, visibility and authorization are checked again at
              confirmation.
            </p>
            <Button
              busy={busy}
              disabled={!preview?.permitted_fields.length}
              onClick={() =>
                void action(async () => {
                  if (!preview) return;
                  const { data } = await mutate<Disclosure>(
                    `${base}/candidates/${candidate}/disclosures`,
                    {
                      preview_id: preview.preview_id,
                      preview_hash: preview.preview_hash,
                      confirm: true,
                    },
                  );
                  setPreview(null);
                  setMessage(
                    `Disclosure result: ${label(data.state)}. ${label(data.result_category ?? "pending")}. No delivery is assumed; automatic resend is disabled.`,
                  );
                })
              }
            >
              Confirm disclosure
            </Button>
            <Button disabled={busy} onClick={() => setPreview(null)}>
              Cancel disclosure
            </Button>
          </Dialog>
        </>
      )}
    </AppShell>
  );
}
