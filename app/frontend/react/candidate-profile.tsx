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
  PlatformNavigation,
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
  reviewable_resume_id?: string | null;
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
  error_message?: string;
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
      "Only companies you explicitly approve can find you.",
    ],
    [
      "MATCHING_ROLES",
      "Matching roles",
      "Recruiters with active roles matching your preferences can find you.",
    ],
    [
      "APPLIED_ROLES_ONLY",
      "Applied roles only",
      "Only hiring teams for jobs you apply to can see your profile.",
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
        <legend>Who can find you?</legend>
        <p className="visibility-explanation">
          This controls recruiter search visibility. Uploading a resume does not
          make your profile public. Choose Not looking to keep it hidden while
          you finish; you can change this later.
        </p>
        <div className="profile-visibility-list">
          {modes.map(([mode, label]) => (
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
            </div>
          ))}
        </div>
        <p className="selected-visibility-help">
          {modes.find(([mode]) => mode === draft.visibility)?.[2]}
        </p>
      </fieldset>
      {draft.visibility === "APPROVED_RECRUITERS" && (
        <div className="approved-audience-note" role="status">
          {list(draft.approved_tenant_ids).length
            ? `Your existing approval covers ${list(draft.approved_tenant_ids).length} ${list(draft.approved_tenant_ids).length === 1 ? "company" : "companies"}. Saving keeps this audience unchanged. Choose another visibility option to change who can discover you.`
            : "You have no approved companies yet. Choose Matching roles, Applied roles only, or Not looking to continue."}
        </div>
      )}
      <Alert tone="gold">
        Saving applies your selected audience. “Not looking” hides your profile
        from recruiter searches. You can update this choice at any time.
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
  const message =
    state.error_message ||
    (terminal
      ? state.scan_status === "REJECTED"
        ? "This file could not pass the safety or file-integrity check. Try another copy."
        : "The security scanner is temporarily unavailable. Please retry your upload shortly."
      : state.parse_status === "PARSE_FAILED"
        ? "Resume parsing failed. Try an unlocked PDF or Word document with readable text. You can also enter details yourself."
        : state.parse_status === "READY"
          ? "Resume processing complete."
          : state.parse_status === "REVIEW_REQUIRED"
            ? "Your resume details are ready to review. Nothing is published automatically."
            : state.scan_status === "UPLOADING"
              ? "Uploading your resume…"
              : state.parse_status === "PARSING"
                ? "Reading your resume and extracting details…"
                : "Checking your resume before extraction…");
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
  onReady,
  compact = false,
}: {
  request: PageProps["request"];
  disabled: boolean;
  onApplySuggestions: (
    suggestions: ResumeSuggestion[],
    fillMissingOnly?: boolean,
    resumeId?: string,
  ) => void;
  onReady: () => void;
  compact?: boolean;
}) {
  const [state, setState] = useState<ResumeState | null>(null);
  const [uploading, setUploading] = useState(false);
  const [filename, setFilename] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
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
    setFilename(file.name);
    setSelected(new Set());
    setState({ id: "", scan_status: "UPLOADING", parse_status: "NOT_STARTED" });
    let stage = "prepare";
    try {
      if (!file.size || file.size > 10_485_760)
        throw new Error("Choose a non-empty resume up to 10 MB.");
      const accepted = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ];
      const mime =
        file.type ||
        ({
          pdf: "application/pdf",
          doc: "application/msword",
          docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }[file.name.split(".").pop()?.toLowerCase() ?? ""] ??
          "");
      if (!accepted.includes(mime))
        throw new Error("Choose a PDF, DOC or DOCX resume.");
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
        content_url?: string;
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
            content_type: mime,
            size_bytes: file.size,
            sha256,
          }),
        }),
      );
      stage = "upload";
      const upload = grant.content_url
        ? await request(grant.content_url, {
            method: "PUT",
            headers: {
              "Content-Type": mime,
              "Content-Disposition": 'attachment; filename="resume"',
            },
            body: file,
          })
        : await fetch(grant.upload_url, {
            method: "PUT",
            headers: grant.required_headers,
            body: file,
            cache: "no-store",
          });
      if (!upload.ok) throw new Error("upload");
      stage = "processing";
      for (let remaining = 120; remaining >= 0; remaining--) {
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
        ) {
          if (["READY", "REVIEW_REQUIRED"].includes(data.parse_status)) {
            onApplySuggestions(
              (data.suggestions ?? []).filter(canApplySuggestion),
              true,
              data.id,
            );
          }
          onReady();
          break;
        }
        if (remaining === 0) {
          setState({
            ...data,
            error_message:
              "Processing is taking longer than expected. You can continue reviewing your profile and retry the upload later.",
          });
          break;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
      }
    } catch (failure) {
      if (current === generation.current)
        setState({
          id: "",
          scan_status: "UPLOAD_FAILED",
          parse_status: "NOT_STARTED",
          error_message:
            stage === "prepare" &&
            failure instanceof Error &&
            !["Unable to complete the request.", "Failed to fetch"].includes(
              failure.message,
            )
              ? failure.message
              : stage === "processing"
                ? "We couldn't check the processing status. Please retry shortly."
                : "Your resume couldn't be uploaded. Check your connection and try choosing the file again.",
          manual_entry_available: true,
        });
    } finally {
      if (current === generation.current) {
        setUploading(false);
        onReady();
      }
    }
  };
  const changed = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) void uploadFile(file);
    event.target.value = "";
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
    <section
      className={`profile-upload-card${compact ? " is-compact" : ""}`}
      aria-label="Resume"
    >
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
        <span className="resume-cv" aria-hidden="true">
          <svg width="30" height="34" viewBox="0 0 30 34" fill="none">
            <path
              d="M6 2h12l7 7v22H6V2Z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
            <path
              d="M18 2v8h7M11 17h9M11 22h9M11 27h5"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
            />
          </svg>
        </span>
        <div className="resume-drop-copy">
          <p className="profile-drop-zone-title">
            {compact ? "Your resume" : "Drop your resume"}
          </p>
          <p className="resume-invitation">
            We'll turn it into a profile. You make it yours.
          </p>
          {filename && <p className="resume-filename">{filename}</p>}
        </div>
        <div className="resume-file-control">
          <Button
            disabled={disabled || uploading}
            busy={uploading}
            onClick={() => fileInput.current?.click()}
          >
            {uploading
              ? "Reading your resume…"
              : filename
                ? "Choose another resume"
                : "Choose your resume"}
            <span aria-hidden="true"> ↗</span>
          </Button>
          <p className="resume-file-help">PDF, DOC or DOCX · Up to 10 MB</p>
          <div className="resume-native-input">
            <Field
              label="Choose PDF, DOC, or DOCX, up to 10 MB"
              help={"PDF, DOC or DOCX · Up to 10 MB"}
            >
              {(props) => (
                <input
                  {...props}
                  ref={fileInput}
                  tabIndex={-1}
                  type="file"
                  accept=".pdf,.doc,.docx"
                  disabled={disabled || uploading}
                  onChange={changed}
                />
              )}
            </Field>
          </div>
        </div>
      </div>
      {state && (
        <details
          className="resume-processing-details"
          open={
            uploading ||
            Boolean(state.error_message) ||
            ["SCAN_FAILED", "REJECTED"].includes(state.scan_status) ||
            state.parse_status === "PARSE_FAILED"
          }
        >
          <summary>
            {uploading ? "Reading your resume…" : "Resume processing details"}
          </summary>
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
                    canApplySuggestion(fact)
                      ? [suggestionKey(fact, index)]
                      : [],
                  ),
                ),
              )
            }
            onApply={() => {
              const approved = suggestions.filter((fact, index) =>
                selected.has(suggestionKey(fact, index)),
              );
              onApplySuggestions(approved, false, state.id);
              setSelected(new Set());
            }}
          />
        </details>
      )}
      {!state && !compact && (
        <div className="resume-promises">
          <div>
            <span>Recruiters see</span>
            <strong>Role, skills, availability and your work</strong>
          </div>
          <div>
            <span>You control</span>
            <strong>Visibility, work mode and preferences</strong>
          </div>
          <div>
            <span>After upload</span>
            <strong>Review your story. Fill in only what's missing.</strong>
          </div>
        </div>
      )}
    </section>
  );
}

export function CandidateProfilePage({ request }: PageProps) {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const resumeBaseline = useRef<Draft>(emptyDraft());
  const [etag, setEtag] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [conflict, setConflict] = useState<ConflictPayload | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [started, setStarted] = useState(false);
  const [resumeAdded, setResumeAdded] = useState(false);
  const [reviewedResumeId, setReviewedResumeId] = useState<string | null>(null);

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
        resumeBaseline.current = toDraft(data);
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
  if (!profile)
    return (
      <AppShell title="Control your profile">
        <ErrorState onRetry={() => setAttempt((value) => value + 1)} />
      </AppShell>
    );

  const payload = () => ({
    ...(reviewedResumeId || profile.reviewable_resume_id
      ? { reviewed_resume_id: reviewedResumeId || profile.reviewable_resume_id }
      : {}),
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
    if (
      draft.visibility === "APPROVED_RECRUITERS" &&
      (!list(draft.approved_tenant_ids).length ||
        list(draft.approved_tenant_ids).some(
          (id) =>
            !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
              id,
            ),
        ))
    ) {
      setError(
        "Choose Matching roles, Applied roles only, or Not looking. There are no valid company approvals to use yet. Your changes have not been saved.",
      );
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    setConflict(null);
    const attempted = payload();
    let detailsSaved = false;
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
      // Keep the new version if the separate audience save fails, so retry is safe.
      setEtag(savedEtag ?? etag);
      setProfile(saved);
      detailsSaved = true;
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
        visibility: {
          ...saved.visibility,
          mode: draft.visibility,
          approved_tenant_ids: list(draft.approved_tenant_ids),
        },
      };
      setProfile(combined);
      setDraft(toDraft(combined));
      setEtag(visibilityEtag ?? savedEtag ?? etag);
      setMessage(
        "Profile and visibility saved. Your current audience choice is active.",
      );
    } catch {
      setError(
        detailsSaved
          ? "Your profile details were saved, but visibility could not be updated. Your previous audience remains active. Retry Save to apply your choice."
          : "The profile could not be saved. Your edits remain on this page for review.",
      );
    } finally {
      setBusy(false);
    }
  };
  const showActionFeedback = () =>
    requestAnimationFrame(() => {
      const feedback = document.getElementById("profile-action-feedback");
      feedback?.focus({ preventScroll: true });
      feedback?.scrollIntoView({ block: "nearest" });
    });
  const publish = async () => {
    if (busy) return;
    setError("");
    setMessage("");
    if (missing.length) {
      setError(
        `Before publishing, add: ${missing.join(", ")}. Use the missing-details buttons above to complete them, then save your profile.`,
      );
      showActionFeedback();
      return;
    }
    if (JSON.stringify(draft) !== JSON.stringify(toDraft(profile))) {
      setError(
        "Your changes haven’t been saved yet. Choose Save profile and visibility, then Publish profile.",
      );
      showActionFeedback();
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await request("/api/v1/candidate/profile/publish", {
        method: "POST",
        headers: { "If-Match": etag, "Idempotency-Key": crypto.randomUUID() },
      });
      if (response.status === 422) {
        const problem = (await response.json()) as {
          errors?: Record<string, unknown>;
        };
        const actions: Record<string, string> = {
          full_name: "Add your full name",
          location: "Add your location",
          skills: "Add your skills",
          current_role: "Add your current role",
          experience_years: "Add your experience in years",
          notice_period: "Add your notice period",
          meaningful_work: "Describe your meaningful work",
          role_categories: "Choose your preferred roles",
          preferred_locations: "Choose your preferred locations",
          work_arrangements: "Choose a work arrangement",
          resume:
            "Upload a resume, wait for processing to finish, then review its extracted details",
          visibility: "Save your visibility choice",
          consent: "Save your visibility choice to confirm consent",
        };
        const issues = Object.keys(problem.errors ?? {})
          .map((key) => actions[key])
          .filter(Boolean);
        setError(
          issues.length
            ? `Publication blocked: ${[...new Set(issues)].join("; ")}. Then save and publish again.`
            : "Publication could not be validated. Reload your saved profile and review the required details before retrying.",
        );
        return;
      }
      if (response.status === 409) {
        setError(
          "Your profile changed since this page loaded. Reload to review the latest saved details before publishing.",
        );
        return;
      }
      if ([401, 403, 404].includes(response.status)) {
        setError(
          "Your candidate session is no longer available. Sign in to Candidate Platform again before publishing.",
        );
        return;
      }
      const { data, etag: nextEtag } =
        await responseJson<CandidateProfile>(response);
      setProfile(data);
      setDraft(toDraft(data));
      setEtag(nextEtag ?? etag);
      setMessage(
        "Profile publication saved. Recruiter access still follows your visibility choice.",
      );
    } catch {
      setError(
        "We couldn’t reach the publication service. Your saved profile is unchanged. Please try again shortly.",
      );
    } finally {
      setBusy(false);
      showActionFeedback();
    }
  };

  const missing = [
    !draft.full_name.trim() ? "full name" : "",
    !draft.location.trim() ? "location" : "",
    !list(draft.skills).length ? "skills" : "",
    !draft.current_role.trim() ? "Current role" : "",
    !draft.experience_years ? "Experience in years" : "",
    !draft.notice_period.trim() ? "Notice period" : "",
    !draft.meaningful_work.trim() ? "Meaningful work" : "",
    !list(draft.role_categories).length ? "Preferred roles" : "",
    !list(draft.preferred_locations).length ? "Preferred locations" : "",
    !draft.work_arrangements.length ? "Work arrangements" : "",
  ].filter(Boolean);
  const focusMissing = (label: string) => {
    const fieldLabel = Array.from(
      document.querySelectorAll<HTMLLabelElement>(".profile-form label"),
    ).find(
      (element) =>
        element.textContent?.trim().toLowerCase() === label.toLowerCase(),
    );
    const input =
      label === "Work arrangements"
        ? document.querySelector<HTMLInputElement>(".profile-choice-grid input")
        : fieldLabel?.htmlFor
          ? document.getElementById(fieldLabel.htmlFor)
          : null;
    if (input) {
      const section = input.closest("details");
      if (section) section.open = true;
      input.focus({ preventScroll: true });
      input.scrollIntoView({
        block: "center",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
    }
  };

  return (
    <div className={`candidate-profile-page${started ? " is-reviewing" : ""}`}>
      <AppShell
        title="Right person. Right problem."
        navigation={
          <>
            <PlatformNavigation active="candidate" />
            <Button
              variant="secondary"
              onClick={async () => {
                const response = await request("/api/v1/session/sign-out", {
                  method: "DELETE",
                });
                if (response.ok) location.replace("/");
                else setError("Sign-out failed. Please try again.");
              }}
            >
              Logout
            </Button>
          </>
        }
      >
        <div className="candidate-intro">
          <span className="candidate-eyebrow">YOUR NEXT CHAPTER</span>
          <p>
            {started
              ? "A little more you. Review your story and choose what comes next."
              : "Your experience deserves the right opportunity. Start with your resume."}
          </p>
          <ol className="candidate-steps" aria-label="Profile setup">
            <li
              className={!started ? "is-current" : resumeAdded ? "is-done" : ""}
              aria-current={!started ? "step" : undefined}
            >
              <span>{resumeAdded ? "✓" : "1"}</span> Add your resume
            </li>
            <li
              className={started ? "is-current" : ""}
              aria-current={started ? "step" : undefined}
            >
              <span>2</span> Make it yours
            </li>
            <li>
              <span>3</span> Choose your visibility
            </li>
          </ol>
        </div>
        {error && <Alert>{error}</Alert>}
        {message && (
          <div className="candidate-feedback">
            <StatusMessage>{message}</StatusMessage>
          </div>
        )}
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
        <ResumeUploader
          compact={started}
          request={request}
          disabled={busy}
          onReady={() => setStarted(true)}
          onApplySuggestions={(
            suggestions,
            fillMissingOnly = false,
            resumeId,
          ) => {
            if (resumeId) setReviewedResumeId(resumeId);
            setResumeAdded(true);
            setDraft((current) => {
              if (!fillMissingOnly)
                return applyResumeSuggestions(current, suggestions);
              const baseline = resumeBaseline.current;
              const accepted = suggestions.filter(
                (fact) =>
                  JSON.stringify(current[fact.fact_type as keyof Draft]) ===
                  JSON.stringify(baseline[fact.fact_type as keyof Draft]),
              );
              const next = { ...current };
              // A new resume replaces saved resume facts in the draft, not edits made here.
              for (const key of [
                "full_name",
                "location",
                "headline",
                "current_role",
                "current_company",
                "experience_years",
                "skills",
              ] as const) {
                if (current[key] === baseline[key]) next[key] = "";
              }
              if (
                JSON.stringify(current.employment_history) ===
                JSON.stringify(baseline.employment_history)
              )
                next.employment_history = [];
              const result = applyResumeSuggestions(next, accepted);
              const tracked = { ...baseline };
              for (const key of Object.keys(baseline) as Array<keyof Draft>) {
                if (
                  JSON.stringify(current[key]) === JSON.stringify(baseline[key])
                ) {
                  Object.assign(tracked, { [key]: result[key] });
                }
              }
              resumeBaseline.current = tracked;
              return result;
            });
            setStarted(true);
            setMessage(
              "Your profile preview is ready. Check the details below — nothing is saved yet.",
            );
          }}
        />
        {!started && (
          <div className="candidate-start-actions">
            <Button variant="secondary" onClick={() => setStarted(true)}>
              {draft.full_name
                ? "Review my existing profile →"
                : "I'll add my details myself →"}
            </Button>
          </div>
        )}
        {started && (
          <div className="candidate-review-layout">
            <section
              className="profile-completion"
              aria-label="Profile completeness"
            >
              <div>
                <strong>
                  {missing.length
                    ? `${missing.length} required ${missing.length === 1 ? "detail is" : "details are"} missing`
                    : "Required details complete"}
                </strong>
                <span>{Math.round(((10 - missing.length) / 10) * 100)}%</span>
              </div>
              <progress
                max={10}
                value={10 - missing.length}
                aria-label="Core profile completeness"
              />
              <p role="status" aria-live="polite">
                {missing.length
                  ? `Still to add: ${missing.join(", ")}.`
                  : "Core details are ready for your review."}
              </p>
              {missing.length > 0 && (
                <div
                  className="missing-detail-actions"
                  aria-label="Required missing details"
                >
                  {missing.map((label) => (
                    <Button
                      key={label}
                      variant="secondary"
                      onClick={() => focusMissing(label)}
                    >
                      Add {label} <span aria-hidden="true">→</span>
                    </Button>
                  ))}
                </div>
              )}
              <p className="profile-readiness-note">
                Complete all the details above before publishing. Publishing
                also requires a successfully processed resume and a saved
                visibility choice. No additional documents are required.
              </p>
            </section>
            <form
              className="profile-form"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
              noValidate
            >
              <details className="profile-conversation" open>
                <summary>
                  Profile preview
                  <small>
                    A few details help recruiters understand fit without asking
                    you to repeat your resume.
                  </small>
                </summary>
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
                    <div className="profile-field-grid">
                      <div className="notice-conversation">
                        <p>When could you start?</p>
                        <div className="preview-chips">
                          {[
                            "Immediate",
                            "15 days",
                            "30 days",
                            "60 days",
                            "90 days",
                          ].map((notice) => (
                            <Button
                              key={notice}
                              variant="secondary"
                              aria-pressed={draft.notice_period === notice}
                              disabled={busy}
                              onClick={() =>
                                setDraft((value) => ({
                                  ...value,
                                  notice_period: notice,
                                }))
                              }
                            >
                              {notice}
                            </Button>
                          ))}
                        </div>
                      </div>
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
              </details>
              <details className="profile-conversation">
                <summary>
                  Career history
                  <small>Review roles, dates and the work you owned</small>
                </summary>
                <EmploymentEditor
                  records={draft.employment_history}
                  disabled={busy}
                  onChange={(employment_history) =>
                    setDraft((value) => ({ ...value, employment_history }))
                  }
                />
              </details>
              <details className="profile-conversation" open>
                <summary>
                  <strong>Your next opportunity</strong>
                  <small>
                    Required · Choose the roles, places and work style you
                    prefer.
                  </small>
                </summary>
                <Preferences
                  draft={draft}
                  disabled={busy}
                  setDraft={setDraft}
                />
              </details>
              <details className="profile-conversation" open>
                <summary>
                  <strong>Who can see your profile?</strong>
                  <small>
                    Choose your audience. Keep it hidden until you’re ready.
                  </small>
                </summary>
                <VisibilityConsent
                  draft={draft}
                  disabled={busy}
                  setDraft={setDraft}
                />
              </details>
              <section className="profile-work-card">
                <h2>What’s the most meaningful thing you’ve built?</h2>{" "}
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
              </section>
              <div
                id="profile-action-feedback"
                className="profile-action-feedback"
                tabIndex={-1}
                aria-live="polite"
              >
                {(error || message) && (
                  <p data-error={Boolean(error)}>{error || message}</p>
                )}
              </div>
              <p className="ui-help">
                Saving confirms that you’ve reviewed the profile details
                extracted from your resume.
              </p>
              <div className="profile-actions">
                <p className="profile-save-note">
                  {JSON.stringify(draft) !== JSON.stringify(toDraft(profile))
                    ? "You have unsaved changes"
                    : "Your saved profile is up to date"}
                  <small>
                    {missing.length
                      ? `Complete ${missing.length} missing details before publishing. You can save your draft now.`
                      : "Save your details and visibility choice before publishing."}
                  </small>
                </p>
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
          </div>
        )}
      </AppShell>
    </div>
  );
}
