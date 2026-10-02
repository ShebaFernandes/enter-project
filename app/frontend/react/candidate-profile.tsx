import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent as ReactDragEvent,
} from "react";
import type { PageProps } from "./mount";
import type { ConflictPayload } from "../shared/conflict-resolution";
import {
  Alert,
  AppShell,
  Button,
  Card,
  Checkbox,
  Chip,
  ConflictPanel,
  ErrorState,
  Field,
  Loading,
  Radio,
  Select,
  StatusMessage,
  Textarea,
  TextInput,
} from "./components";
import { responseJson } from "../shared/api-client";

type ValueState = "CONFIRMED" | "SUGGESTED" | "AMBIGUOUS" | "MISSING";
type VisibilityMode =
  | "APPROVED_RECRUITERS"
  | "MATCHING_ROLES"
  | "APPLIED_ROLES_ONLY"
  | "NOT_LOOKING";
type EmploymentRecord = {
  id?: string;
  company: string;
  role_title: string | null;
  start_date: string | null;
  end_date: string | null;
  start_date_state: ValueState;
  end_date_state: ValueState;
  is_current: boolean;
  employment_type: string;
  employment_type_state: ValueState;
  provenance: "CANDIDATE_REPORTED" | "RESUME_EXTRACTED";
  confidence?: number | null;
  source_spans: unknown[];
  version?: number;
};
type Visibility = {
  mode: VisibilityMode;
  approved_tenant_ids?: string[];
  matching_preferences?: Record<string, unknown>;
  version: number;
};
type CandidateProfile = {
  id: string;
  full_name: string;
  location: Record<string, unknown>;
  headline: string | null;
  current_role: string | null;
  current_company: string | null;
  experience_years: string | number;
  skills: string[];
  employment_history: EmploymentRecord[];
  role_categories: string[];
  preferred_locations: string[];
  work_arrangements: string[];
  meaningful_work: string | null;
  notice_period: string | null;
  availability_date: string | null;
  compensation: Record<string, unknown> | null;
  professional_links: string[];
  contact_preferences: Record<string, unknown>;
  profile_state: string;
  visibility: Visibility;
  version: number;
};
type Draft = {
  full_name: string;
  location: string;
  headline: string;
  current_role: string;
  current_company: string;
  experience_years: string;
  skills: string;
  employment_history: EmploymentRecord[];
  role_categories: string;
  preferred_locations: string;
  work_arrangements: string[];
  meaningful_work: string;
  notice_period: string;
  availability_date: string;
  visibility: VisibilityMode;
  approved_tenant_ids: string;
};
type ResumeSuggestion = {
  id?: string;
  fact_type?: string;
  value?: unknown;
  confidence?: number | null;
  source_spans?: unknown[];
  state?: string;
};
type ResumeState = {
  id: string;
  scan_status: string;
  parse_status: string;
  manual_entry_available?: boolean;
  suggestions?: ResumeSuggestion[];
};

const valueStates: ValueState[] = [
  "CONFIRMED",
  "SUGGESTED",
  "AMBIGUOUS",
  "MISSING",
];
const employmentTypes = [
  "PERMANENT",
  "INTERNSHIP",
  "APPRENTICESHIP",
  "FIXED_TERM_CONTRACT",
  "CONSULTING",
  "SEASONAL",
  "OTHER_TEMPORARY",
  "OTHER",
  "UNKNOWN",
];
const arrangements = ["FLEXIBLE", "REMOTE", "HYBRID", "ON_SITE"];

const list = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
const displayLocation = (location: Record<string, unknown>) =>
  String(location.display ?? location.city ?? location.normalized ?? "");
const freshEmployment = (): EmploymentRecord => ({
  company: "",
  role_title: null,
  start_date: null,
  end_date: null,
  start_date_state: "MISSING",
  end_date_state: "MISSING",
  is_current: false,
  employment_type: "UNKNOWN",
  employment_type_state: "MISSING",
  provenance: "CANDIDATE_REPORTED",
  source_spans: [],
});
const toDraft = (profile: CandidateProfile): Draft => ({
  full_name: profile.full_name,
  location: displayLocation(profile.location),
  headline: profile.headline ?? "",
  current_role: profile.current_role ?? "",
  current_company: profile.current_company ?? "",
  experience_years: String(profile.experience_years),
  skills: profile.skills.join(", "),
  employment_history: profile.employment_history,
  role_categories: profile.role_categories.join(", "),
  preferred_locations: profile.preferred_locations.join(", "),
  work_arrangements: profile.work_arrangements,
  meaningful_work: profile.meaningful_work ?? "",
  notice_period: profile.notice_period ?? "",
  availability_date: profile.availability_date ?? "",
  visibility: profile.visibility.mode,
  approved_tenant_ids: (profile.visibility.approved_tenant_ids ?? []).join(
    ", ",
  ),
});
const emptyDraft = (): Draft => ({
  full_name: "",
  location: "",
  headline: "",
  current_role: "",
  current_company: "",
  experience_years: "",
  skills: "",
  employment_history: [],
  role_categories: "",
  preferred_locations: "",
  work_arrangements: [],
  meaningful_work: "",
  notice_period: "",
  availability_date: "",
  visibility: "NOT_LOOKING",
  approved_tenant_ids: "",
});

const suggestionKey = (suggestion: ResumeSuggestion, index: number) =>
  suggestion.id ?? `${suggestion.fact_type ?? "fact"}-${index}`;
const suggestionName = (suggestion: ResumeSuggestion) =>
  String(suggestion.fact_type ?? "suggested fact").replaceAll("_", " ");
const applicableSuggestionTypes = new Set([
  "full_name",
  "location",
  "headline",
  "current_role",
  "current_company",
  "experience_years",
  "skills",
  "role_categories",
  "preferred_locations",
  "work_arrangements",
  "meaningful_work",
  "notice_period",
  "availability_date",
  "employment_history",
]);
const canApplySuggestion = (suggestion: ResumeSuggestion) =>
  applicableSuggestionTypes.has(suggestion.fact_type ?? "");
const suggestionText = (value: unknown) => {
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return String(record.display ?? record.company ?? JSON.stringify(value));
  }
  return String(value ?? "");
};
const suggestedEmployment = (value: unknown): EmploymentRecord[] => {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const record = item as Record<string, unknown>;
    if (typeof record.company !== "string" || !record.company.trim()) return [];
    const start =
      typeof record.start_date === "string" ? record.start_date : null;
    const end = typeof record.end_date === "string" ? record.end_date : null;
    const employmentType =
      typeof record.employment_type === "string" &&
      employmentTypes.includes(record.employment_type)
        ? record.employment_type
        : "UNKNOWN";
    return [
      {
        company: record.company,
        role_title:
          typeof record.role_title === "string" ? record.role_title : null,
        start_date: start,
        end_date: end,
        start_date_state: start ? "SUGGESTED" : "MISSING",
        end_date_state: end ? "SUGGESTED" : "MISSING",
        is_current: record.is_current === true,
        employment_type: employmentType,
        employment_type_state:
          employmentType === "UNKNOWN" ? "MISSING" : "SUGGESTED",
        provenance: "RESUME_EXTRACTED",
        confidence:
          typeof record.confidence === "number" ? record.confidence : null,
        source_spans: Array.isArray(record.source_spans)
          ? record.source_spans
          : [],
      } satisfies EmploymentRecord,
    ];
  });
};
const applyResumeSuggestions = (
  draft: Draft,
  suggestions: ResumeSuggestion[],
): Draft => {
  const next = { ...draft };
  for (const suggestion of suggestions) {
    const value = suggestion.value;
    switch (suggestion.fact_type) {
      case "full_name":
      case "headline":
      case "current_role":
      case "current_company":
      case "meaningful_work":
      case "notice_period":
      case "availability_date":
        if (typeof value === "string") next[suggestion.fact_type] = value;
        break;
      case "location":
        if (typeof value === "string") next.location = value;
        else if (value && typeof value === "object")
          next.location = displayLocation(value as Record<string, unknown>);
        break;
      case "experience_years":
        if (typeof value === "string" || typeof value === "number")
          next.experience_years = String(value);
        break;
      case "skills":
      case "role_categories":
      case "preferred_locations":
        if (Array.isArray(value))
          next[suggestion.fact_type] = value.map(String).join(", ");
        break;
      case "work_arrangements":
        if (Array.isArray(value))
          next.work_arrangements = value
            .map(String)
            .filter((item) => arrangements.includes(item));
        break;
      case "employment_history": {
        const records = suggestedEmployment(value);
        if (records.length) next.employment_history = records;
        break;
      }
    }
  }
  return next;
};

function ProfileSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return <Card title={title}>{children}</Card>;
}

function EmploymentEditor({
  records,
  disabled,
  onChange,
}: {
  records: EmploymentRecord[];
  disabled: boolean;
  onChange: (records: EmploymentRecord[]) => void;
}) {
  const addButton = useRef<HTMLButtonElement>(null);
  const update = (index: number, patch: Partial<EmploymentRecord>) =>
    onChange(
      records.map((record, i) =>
        i === index ? { ...record, ...patch } : record,
      ),
    );
  return (
    <ProfileSection title="Employment history">
      <p>
        Confirm only facts you know. Missing or uncertain dates may stay
        unconfirmed.
      </p>
      <div className="profile-employment-list">
        {records.map((record, index) => (
          <fieldset
            className="profile-employment"
            key={record.id ?? `new-${index}`}
          >
            <legend>Employment record {index + 1}</legend>
            <div className="profile-record-meta">
              <Chip
                tone={
                  record.provenance === "RESUME_EXTRACTED" ? "gold" : "sage"
                }
              >
                {record.provenance === "RESUME_EXTRACTED"
                  ? "Resume extracted — review required"
                  : "Candidate reported"}
              </Chip>
            </div>
            <div className="profile-field-grid">
              <Field label="Company">
                {(props) => (
                  <TextInput
                    {...props}
                    required
                    maxLength={300}
                    disabled={disabled}
                    value={record.company}
                    onChange={(event) =>
                      update(index, { company: event.target.value })
                    }
                  />
                )}
              </Field>
              <Field label="Role title">
                {(props) => (
                  <TextInput
                    {...props}
                    maxLength={300}
                    disabled={disabled}
                    value={record.role_title ?? ""}
                    onChange={(event) =>
                      update(index, { role_title: event.target.value || null })
                    }
                  />
                )}
              </Field>
              <Field label="Start date">
                {(props) => (
                  <TextInput
                    {...props}
                    type="date"
                    disabled={disabled}
                    value={record.start_date ?? ""}
                    onChange={(event) =>
                      update(index, { start_date: event.target.value || null })
                    }
                  />
                )}
              </Field>
              <Field label="Start-date confidence">
                {(props) => (
                  <Select
                    {...props}
                    disabled={disabled}
                    value={record.start_date_state}
                    onChange={(event) =>
                      update(index, {
                        start_date_state: event.target.value as ValueState,
                      })
                    }
                  >
                    {valueStates.map((state) => (
                      <option key={state}>{state}</option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="End date">
                {(props) => (
                  <TextInput
                    {...props}
                    type="date"
                    disabled={disabled || record.is_current}
                    value={record.end_date ?? ""}
                    onChange={(event) =>
                      update(index, { end_date: event.target.value || null })
                    }
                  />
                )}
              </Field>
              <Field label="End-date confidence">
                {(props) => (
                  <Select
                    {...props}
                    disabled={disabled || record.is_current}
                    value={record.end_date_state}
                    onChange={(event) =>
                      update(index, {
                        end_date_state: event.target.value as ValueState,
                      })
                    }
                  >
                    {valueStates.map((state) => (
                      <option key={state}>{state}</option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Employment type">
                {(props) => (
                  <Select
                    {...props}
                    disabled={disabled}
                    value={record.employment_type}
                    onChange={(event) =>
                      update(index, {
                        employment_type: event.target.value,
                        employment_type_state: "CONFIRMED",
                      })
                    }
                  >
                    {employmentTypes.map((type) => (
                      <option key={type}>{type}</option>
                    ))}
                  </Select>
                )}
              </Field>
              <Checkbox
                label="This is my current role"
                disabled={disabled}
                checked={record.is_current}
                onChange={(event) =>
                  update(index, {
                    is_current: event.target.checked,
                    ...(event.target.checked
                      ? { end_date: null, end_date_state: "MISSING" }
                      : {}),
                  })
                }
              />
            </div>
            <Button
              variant="secondary"
              disabled={disabled}
              onClick={() => {
                onChange(records.filter((_, i) => i !== index));
                requestAnimationFrame(() => addButton.current?.focus());
              }}
            >
              Remove employment record {index + 1}
            </Button>
          </fieldset>
        ))}
      </div>
      <Button
        ref={addButton}
        variant="secondary"
        disabled={disabled}
        onClick={() => onChange([...records, freshEmployment()])}
      >
        Add employment record
      </Button>
    </ProfileSection>
  );
}

function Preferences({
  draft,
  disabled,
  setDraft,
}: {
  draft: Draft;
  disabled: boolean;
  setDraft: React.Dispatch<React.SetStateAction<Draft>>;
}) {
  return (
    <ProfileSection title="Opportunity preferences">
      <Field label="Preferred roles" help="Separate roles with commas.">
        {(props) => (
          <TextInput
            {...props}
            disabled={disabled}
            value={draft.role_categories}
            onChange={(event) =>
              setDraft((value) => ({
                ...value,
                role_categories: event.target.value,
              }))
            }
          />
        )}
      </Field>
      <Field label="Preferred locations" help="Separate locations with commas.">
        {(props) => (
          <TextInput
            {...props}
            disabled={disabled}
            value={draft.preferred_locations}
            onChange={(event) =>
              setDraft((value) => ({
                ...value,
                preferred_locations: event.target.value,
              }))
            }
          />
        )}
      </Field>
      <fieldset>
        <legend>Work arrangements</legend>
        <div className="profile-choice-grid">
          {arrangements.map((arrangement) => (
            <Checkbox
              key={arrangement}
              label={arrangement.replaceAll("_", " ").toLowerCase()}
              disabled={disabled}
              checked={draft.work_arrangements.includes(arrangement)}
              onChange={(event) =>
                setDraft((value) => ({
                  ...value,
                  work_arrangements: event.target.checked
                    ? [...value.work_arrangements, arrangement]
                    : value.work_arrangements.filter(
                        (item) => item !== arrangement,
                      ),
                }))
              }
            />
          ))}
        </div>
      </fieldset>
    </ProfileSection>
  );
}

function VisibilityConsent({
  draft,
  disabled,
  setDraft,
}: {
  draft: Draft;
  disabled: boolean;
  setDraft: React.Dispatch<React.SetStateAction<Draft>>;
}) {
  const modes: Array<[VisibilityMode, string, string]> = [
    [
      "APPROVED_RECRUITERS",
      "Approved recruiters",
      "Only the company tenants you explicitly list.",
    ],
    [
      "MATCHING_ROLES",
      "Matching roles",
      "Only active roles matching your saved deterministic preferences.",
    ],
    [
      "APPLIED_ROLES_ONLY",
      "Applied roles only",
      "Only authorized teams for roles you applied to.",
    ],
    [
      "NOT_LOOKING",
      "Not looking",
      "Hide the profile from recruiter discovery.",
    ],
  ];
  return (
    <ProfileSection title="Visibility and consent">
      <fieldset>
        <legend>Who may discover this profile?</legend>
        <div className="profile-visibility-list">
          {modes.map(([mode, label, help]) => (
            <div key={mode}>
              <Radio
                label={label}
                name="visibility"
                value={mode}
                disabled={disabled}
                checked={draft.visibility === mode}
                onChange={() =>
                  setDraft((value) => ({ ...value, visibility: mode }))
                }
              />
              <p className="ui-help">{help}</p>
            </div>
          ))}
        </div>
      </fieldset>
      {draft.visibility === "APPROVED_RECRUITERS" && (
        <Field
          label="Approved company tenant IDs"
          help="At least one tenant ID is required; separate IDs with commas."
        >
          {(props) => (
            <TextInput
              {...props}
              disabled={disabled}
              value={draft.approved_tenant_ids}
              onChange={(event) =>
                setDraft((value) => ({
                  ...value,
                  approved_tenant_ids: event.target.value,
                }))
              }
            />
          )}
        </Field>
      )}
      <Alert tone="gold">
        Saving this section records your affirmative recruiting-discovery
        consent for the selected audience. You can choose Not looking to hide
        the profile immediately.
      </Alert>
    </ProfileSection>
  );
}

function ScanState({
  state,
  selected,
  onToggle,
  onSelectAll,
  onApply,
}: {
  state: ResumeState | null;
  selected: Set<string>;
  onToggle: (key: string, checked: boolean) => void;
  onSelectAll: () => void;
  onApply: () => void;
}) {
  if (!state) return <StatusMessage>No file selected.</StatusMessage>;
  const terminal = ["REJECTED", "SCAN_FAILED"].includes(state.scan_status);
  const message = terminal
    ? "Security scanning did not succeed. The resume remains unavailable; continue with manual entry."
    : state.parse_status === "PARSE_FAILED"
      ? "Resume parsing failed. Continue by entering profile and employment facts manually."
      : state.parse_status === "READY"
        ? "Resume processing complete."
        : state.parse_status === "REVIEW_REQUIRED"
          ? "Review every suggested fact before using it. Nothing is published automatically."
          : "Resume is quarantined while security checks continue.";
  return (
    <div className="ui-stack">
      <StatusMessage>{message}</StatusMessage>
      {(terminal || state.manual_entry_available) && (
        <a href="#profile-facts">Continue with manual profile entry</a>
      )}
      {!!state.suggestions?.length && (
        <section aria-labelledby="resume-suggestions-heading">
          <h3 id="resume-suggestions-heading">Review resume suggestions</h3>
          <p>
            Select only accurate details. Applying suggestions changes this
            editable draft; nothing is saved or published until you use the
            profile actions below.
          </p>
          <div className="profile-suggestion-list">
            {state.suggestions.map((fact, index) => {
              const key = suggestionKey(fact, index);
              const name = suggestionName(fact);
              const applicable = canApplySuggestion(fact);
              return (
                <article className="profile-suggestion" key={key}>
                  {applicable ? (
                    <Checkbox
                      label={`Use suggested ${name}`}
                      checked={selected.has(key)}
                      onChange={(event) => onToggle(key, event.target.checked)}
                    />
                  ) : (
                    <h4>{name}</h4>
                  )}
                  <p>Suggested value: {suggestionText(fact.value)}</p>
                  <p className="ui-help">
                    Confidence: {fact.confidence ?? "not supplied"}; source
                    spans: {(fact.source_spans ?? []).length}
                  </p>
                  <Chip tone="gold">
                    {applicable
                      ? "Candidate review required"
                      : "Manual review required"}
                  </Chip>
                </article>
              );
            })}
          </div>
          <div className="profile-suggestion-actions">
            <Button variant="secondary" onClick={onSelectAll}>
              Select all suggestions
            </Button>
            <Button disabled={!selected.size} onClick={onApply}>
              Apply {selected.size} selected suggestion
              {selected.size === 1 ? "" : "s"}
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}

function ResumeUploader({
  request,
  disabled,
  onApplySuggestions,
}: {
  request: PageProps["request"];
  disabled: boolean;
  onApplySuggestions: (suggestions: ResumeSuggestion[]) => void;
}) {
  const [state, setState] = useState<ResumeState | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const generation = useRef(0);
  useEffect(
    () => () => {
      generation.current++;
    },
    [],
  );
  const uploadFile = async (file: File) => {
    const current = ++generation.current;
    setUploading(true);
    setSelected(new Set());
    setState({ id: "", scan_status: "UPLOADING", parse_status: "NOT_STARTED" });
    try {
      if (file.size > 10_485_760) throw new Error("large");
      const accepted = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ];
      if (!accepted.includes(file.type)) throw new Error("type");
      const digest = await crypto.subtle.digest(
        "SHA-256",
        await file.arrayBuffer(),
      );
      const sha256 = [...new Uint8Array(digest)]
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
      const { data: grant } = await responseJson<{
        resume_id: string;
        upload_url: string;
        required_headers?: Record<string, string>;
      }>(
        await request("/api/v1/candidate/resumes/uploads", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({
            filename: file.name,
            content_type: file.type,
            size_bytes: file.size,
            sha256,
          }),
        }),
      );
      const upload = await fetch(grant.upload_url, {
        method: "PUT",
        headers: grant.required_headers,
        body: file,
        cache: "no-store",
      });
      if (!upload.ok) throw new Error("upload");
      for (let remaining = 20; remaining >= 0; remaining--) {
        const { data } = await responseJson<ResumeState>(
          await request(`/api/v1/candidate/resumes/${grant.resume_id}`),
        );
        if (current !== generation.current) return;
        setState(data);
        if (
          ["REJECTED", "SCAN_FAILED"].includes(data.scan_status) ||
          ["REVIEW_REQUIRED", "READY", "PARSE_FAILED"].includes(
            data.parse_status,
          )
        )
          break;
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
      }
    } catch {
      if (current === generation.current)
        setState({
          id: "",
          scan_status: "SCAN_FAILED",
          parse_status: "NOT_STARTED",
          manual_entry_available: true,
        });
    } finally {
      if (current === generation.current) setUploading(false);
    }
  };
  const changed = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) void uploadFile(file);
  };
  const dropped = (event: ReactDragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled || uploading) return;
    const file = event.dataTransfer.files[0];
    if (file) void uploadFile(file);
  };
  const suggestions = state?.suggestions ?? [];
  return (
    <ProfileSection title="Resume">
      <p>
        Your file is uploaded to quarantine and remains unavailable until
        security scanning succeeds.
      </p>
      <div
        className={`profile-drop-zone${dragging ? " is-dragging" : ""}`}
        data-resume-drop-zone
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled && !uploading) setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node))
            setDragging(false);
        }}
        onDrop={dropped}
      >
        <p className="profile-drop-zone-title">
          Drag and drop your resume here
        </p>
        <Field
          label="Choose PDF, DOC, or DOCX, up to 10 MB"
          help="Resume suggestions require your review and never overwrite deliberate edits."
        >
          {(props) => (
            <TextInput
              {...props}
              type="file"
              accept=".pdf,.doc,.docx"
              disabled={disabled || uploading}
              onChange={changed}
            />
          )}
        </Field>
      </div>
      <ScanState
        state={state}
        selected={selected}
        onToggle={(key, checked) =>
          setSelected((current) => {
            const next = new Set(current);
            if (checked) next.add(key);
            else next.delete(key);
            return next;
          })
        }
        onSelectAll={() =>
          setSelected(
            new Set(
              suggestions.flatMap((fact, index) =>
                canApplySuggestion(fact) ? [suggestionKey(fact, index)] : [],
              ),
            ),
          )
        }
        onApply={() => {
          const approved = suggestions.filter((fact, index) =>
            selected.has(suggestionKey(fact, index)),
          );
          onApplySuggestions(approved);
          setSelected(new Set());
        }}
      />
    </ProfileSection>
  );
}

export function CandidateProfilePage({ request }: PageProps) {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [etag, setEtag] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [conflict, setConflict] = useState<ConflictPayload | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const abort = new AbortController();
    setLoading(true);
    setError("");
    setProfile(null);
    setDraft(emptyDraft());
    void request("/api/v1/candidate/profile", { signal: abort.signal })
      .then((response) => responseJson<CandidateProfile>(response))
      .then(({ data, etag: currentEtag }) => {
        setProfile(data);
        setDraft(toDraft(data));
        setEtag(currentEtag ?? "");
      })
      .catch(() => {
        if (!abort.signal.aborted)
          setError(
            "Unable to load the current profile. No saved copy is shown.",
          );
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [attempt, request]);

  if (loading)
    return (
      <AppShell title="Control your profile">
        <Loading label="Loading your current profile…" />
      </AppShell>
    );
  if (error || !profile)
    return (
      <AppShell title="Control your profile">
        <ErrorState onRetry={() => setAttempt((value) => value + 1)} />
      </AppShell>
    );

  const payload = () => ({
    full_name: draft.full_name.trim(),
    location: { display: draft.location.trim() },
    headline: draft.headline.trim() || null,
    current_role: draft.current_role.trim() || null,
    current_company: draft.current_company.trim() || null,
    experience_years: draft.experience_years,
    skills: list(draft.skills),
    employment_history: draft.employment_history.map((record) => {
      const input = { ...record };
      delete input.version;
      return {
        ...input,
        role_title: input.role_title || null,
        confidence: input.confidence ?? null,
        source_spans: input.source_spans ?? [],
      };
    }),
    role_categories: list(draft.role_categories),
    preferred_locations: list(draft.preferred_locations),
    work_arrangements: draft.work_arrangements,
    meaningful_work: draft.meaningful_work || null,
    notice_period: draft.notice_period || null,
    availability_date: draft.availability_date || null,
  });
  const save = async () => {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    setConflict(null);
    const attempted = payload();
    try {
      const response = await request("/api/v1/candidate/profile", {
        method: "PATCH",
        headers: {
          "Content-Type": "application/merge-patch+json",
          "If-Match": etag,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify(attempted),
      });
      if (response.status === 409) {
        const current = (await response.json()) as ConflictPayload;
        setConflict(current);
        if (current.current_etag) setEtag(current.current_etag);
        return;
      }
      const { data: saved, etag: savedEtag } =
        await responseJson<CandidateProfile>(response);
      const visibilityBody: Record<string, unknown> = {
        mode: draft.visibility,
        consent_record_id: crypto.randomUUID(),
      };
      if (draft.visibility === "APPROVED_RECRUITERS")
        visibilityBody.approved_tenant_ids = list(draft.approved_tenant_ids);
      if (draft.visibility === "MATCHING_ROLES")
        visibilityBody.matching_preferences = {
          roles: list(draft.role_categories),
          locations: list(draft.preferred_locations),
          work_arrangements: draft.work_arrangements,
        };
      const { etag: visibilityEtag } = await responseJson<Visibility>(
        await request("/api/v1/candidate/visibility", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "If-Match": savedEtag ?? etag,
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify(visibilityBody),
        }),
      );
      const combined = {
        ...saved,
        visibility: { ...saved.visibility, mode: draft.visibility },
      };
      setProfile(combined);
      setDraft(toDraft(combined));
      setEtag(visibilityEtag ?? savedEtag ?? etag);
      setMessage(
        "Profile and visibility saved. Your current audience choice is active.",
      );
    } catch {
      setError(
        "The profile could not be saved. Your edits remain on this page for review.",
      );
    } finally {
      setBusy(false);
    }
  };
  const publish = async () => {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const { data, etag: nextEtag } = await responseJson<CandidateProfile>(
        await request("/api/v1/candidate/profile/publish", {
          method: "POST",
          headers: { "If-Match": etag, "Idempotency-Key": crypto.randomUUID() },
        }),
      );
      setProfile(data);
      setDraft(toDraft(data));
      setEtag(nextEtag ?? etag);
      setMessage(
        "Profile publication saved. Recruiter access still follows your visibility choice.",
      );
    } catch {
      setError(
        "Profile publication needs more reviewed information, a clean resume and active consent.",
      );
    } finally {
      setBusy(false);
    }
  };

  const missing = [
    !draft.full_name.trim() ? "full name" : "",
    !draft.location.trim() ? "location" : "",
    !list(draft.skills).length ? "skills" : "",
    !draft.employment_history.length ? "employment history review" : "",
  ].filter(Boolean);

  return (
    <div className="candidate-profile-page">
      <AppShell
        title="Control your profile"
        navigation={<a href="/candidate/rights/">Privacy rights centre</a>}
      >
        <p>
          Review every fact before publishing. You decide which recruiters may
          discover it.
        </p>
        <div className="profile-state-row">
          <Chip tone={profile.profile_state === "PUBLISHED" ? "sage" : "gold"}>
            {profile.profile_state.replaceAll("_", " ").toLowerCase()}
          </Chip>
          <span className="ui-help">Server version {profile.version}</span>
        </div>
        {error && <Alert>{error}</Alert>}
        {message && <StatusMessage>{message}</StatusMessage>}
        {conflict && (
          <ConflictPanel
            conflict={conflict}
            onDiscard={() => setAttempt((value) => value + 1)}
            onReview={() => setConflict(null)}
            onResubmit={() => {
              setConflict(null);
              void save();
            }}
          />
        )}
        <Card title="Profile completion">
          <p>
            {missing.length
              ? `Still to review: ${missing.join(", ")}.`
              : "Core profile facts are complete."}{" "}
            A clean reviewed resume and active consent are also required before
            publication.
          </p>
        </Card>
        <form
          className="profile-form"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
          noValidate
        >
          <section id="profile-facts" tabIndex={-1}>
            <ProfileSection title="Profile facts">
              <div className="profile-field-grid">
                <Field label="Full name">
                  {(props) => (
                    <TextInput
                      {...props}
                      autoComplete="name"
                      required
                      maxLength={200}
                      disabled={busy}
                      value={draft.full_name}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          full_name: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
                <Field label="Location">
                  {(props) => (
                    <TextInput
                      {...props}
                      autoComplete="address-level2"
                      required
                      disabled={busy}
                      value={draft.location}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          location: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
                <Field label="Headline">
                  {(props) => (
                    <TextInput
                      {...props}
                      maxLength={300}
                      disabled={busy}
                      value={draft.headline}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          headline: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
                <Field label="Current role">
                  {(props) => (
                    <TextInput
                      {...props}
                      maxLength={200}
                      disabled={busy}
                      value={draft.current_role}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          current_role: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
                <Field label="Current company">
                  {(props) => (
                    <TextInput
                      {...props}
                      maxLength={200}
                      disabled={busy}
                      value={draft.current_company}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          current_company: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
                <Field label="Experience in years">
                  {(props) => (
                    <TextInput
                      {...props}
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      disabled={busy}
                      value={draft.experience_years}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          experience_years: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
              </div>
              <Field label="Skills" help="Separate skills with commas.">
                {(props) => (
                  <TextInput
                    {...props}
                    required
                    disabled={busy}
                    value={draft.skills}
                    onChange={(event) =>
                      setDraft((value) => ({
                        ...value,
                        skills: event.target.value,
                      }))
                    }
                  />
                )}
              </Field>
              <Field
                label="Meaningful work"
                help={`${draft.meaningful_work.length} / 300 characters`}
              >
                {(props) => (
                  <Textarea
                    {...props}
                    maxLength={300}
                    disabled={busy}
                    value={draft.meaningful_work}
                    onChange={(event) =>
                      setDraft((value) => ({
                        ...value,
                        meaningful_work: event.target.value,
                      }))
                    }
                  />
                )}
              </Field>
              <div className="profile-field-grid">
                <Field label="Notice period">
                  {(props) => (
                    <TextInput
                      {...props}
                      disabled={busy}
                      value={draft.notice_period}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          notice_period: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
                <Field label="Availability date">
                  {(props) => (
                    <TextInput
                      {...props}
                      type="date"
                      disabled={busy}
                      value={draft.availability_date}
                      onChange={(event) =>
                        setDraft((value) => ({
                          ...value,
                          availability_date: event.target.value,
                        }))
                      }
                    />
                  )}
                </Field>
              </div>
            </ProfileSection>
          </section>
          <EmploymentEditor
            records={draft.employment_history}
            disabled={busy}
            onChange={(employment_history) =>
              setDraft((value) => ({ ...value, employment_history }))
            }
          />
          <Preferences draft={draft} disabled={busy} setDraft={setDraft} />
          <VisibilityConsent
            draft={draft}
            disabled={busy}
            setDraft={setDraft}
          />
          <ResumeUploader
            request={request}
            disabled={busy}
            onApplySuggestions={(suggestions) => {
              setDraft((current) =>
                applyResumeSuggestions(current, suggestions),
              );
              setError("");
              setMessage(
                `${suggestions.length} resume suggestion${suggestions.length === 1 ? "" : "s"} added to your editable profile. Review the fields, then save when ready.`,
              );
              requestAnimationFrame(() =>
                document.getElementById("profile-facts")?.focus(),
              );
            }}
          />
          <div className="profile-actions">
            <Button type="submit" busy={busy}>
              Save profile and visibility
            </Button>
            <Button
              type="button"
              variant="secondary"
              busy={busy}
              onClick={() => void publish()}
            >
              Publish profile
            </Button>
          </div>
        </form>
      </AppShell>
    </div>
  );
}
