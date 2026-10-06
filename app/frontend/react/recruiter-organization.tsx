import { useCallback, useEffect, useState, type FormEvent } from "react";
import { LinkedinLogo, LinkSimple } from "@phosphor-icons/react";
import {
  Alert,
  AppShell,
  Button,
  Card,
  Checkbox,
  Chip,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  Select,
  StatusMessage,
  Textarea,
  TextInput,
  WorkspaceNavigation,
} from "./components";
import type { PageProps } from "./mount";
import { visualAssets } from "./visual-assets";

type Request = PageProps["request"];
type Unit = {
  id: string;
  name: string;
  description: string;
  status: "ACTIVE" | "INACTIVE";
  version: number;
};
type Opening = {
  id: string;
  business_unit_id: string;
  title: string;
  location: { display?: string };
  work_mode: string;
  employment_type: string;
  description: string;
  company_name: string;
  about_company: string;
  role_summary: string;
  responsibilities: string;
  requirements: string;
  nice_to_have: string;
  state: "DRAFT" | "OPEN" | "PAUSED" | "CLOSED";
  version: number;
  created_at: string;
  updated_at: string;
};
type Synthetic = {
  id: string;
  display_name: string;
  source_type: "RECRUITER_ENTERED_SYNTHETIC";
  source_label: string;
  location: { display?: string };
  experience_years: string;
  skills: string[];
};
type Saved = {
  id: string;
  name: string;
  search_id: string;
  criteria: { context: { type: string; opening_id?: string } };
  changed_since_save: string[];
};
type Publication = {
  internal_state: Opening["state"];
  publication_state: "PUBLISHED" | "UNPUBLISHED";
  public_fields: Record<string, string | null>;
  public_url: string | null;
  source_etag: string;
  preview_digest: string;
};
type Applicant = {
  id: string;
  candidate_id: string;
  name: string;
  headline: string | null;
  current_role: string | null;
  current_company: string | null;
  location: { display?: string };
  experience_years: string | number | null;
  education: Array<Record<string, unknown>>;
  skills: string[];
  employment_history: Array<Record<string, unknown>>;
  professional_links: string[];
  motivation: string;
  candidate_status: string;
  internal_status: string;
  submitted_at: string;
  version: number;
  etag: string;
  resume_available: boolean;
  resume_url: string;
};
const jsonHeaders = () => ({
  "Content-Type": "application/json",
  "Idempotency-Key": crypto.randomUUID(),
});

function PublicationPanel({
  opening,
  base,
  request,
  reload,
}: {
  opening: Opening;
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [preview, setPreview] = useState<Publication>();
  const [reviewed, setReviewed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [message, setMessage] = useState("");
  const [decision, setDecision] = useState<"publish" | "withdraw">();
  const load = useCallback(
    async (show = false) => {
      setMessage("Loading job status…");
      const response = await request(
        `${base}/openings/${opening.id}/publication`,
      );
      if (!response.ok) {
        setMessage("This job's public page is unavailable. Please refresh.");
        return;
      }
      setPreview((await response.json()) as Publication);
      setReviewed(show);
      setMessage(
        show
          ? "Review ready. This is the information candidates will see."
          : "Job status loaded.",
      );
    },
    [base, opening.id, request],
  );
  useEffect(() => void load(false), [load]);
  const changeState = async (state: "OPEN" | "PAUSED" | "CLOSED") => {
    if (!preview) return;
    const response = await request(`${base}/openings/${opening.id}`, {
      method: "PATCH",
      headers: { ...jsonHeaders(), "If-Match": preview.source_etag },
      body: JSON.stringify({ state }),
    });
    if (response.status === 409)
      setMessage("This job changed in another session. Refresh and try again.");
    else if (!response.ok) setMessage("We couldn't update this job.");
    else {
      setMessage(
        state === "OPEN"
          ? "Job is ready. Review the public page, then publish it."
          : "Job status updated.",
      );
      reload();
      void load(false);
    }
  };
  const confirm = async () => {
    if (!preview || !decision) return;
    const response = await request(
      `${base}/openings/${opening.id}/publication/${decision}`,
      {
        method: "POST",
        headers: { ...jsonHeaders(), "If-Match": preview.source_etag },
        body: JSON.stringify({
          confirmed: true,
          ...(decision === "publish"
            ? { preview_digest: preview.preview_digest }
            : {}),
        }),
      },
    );
    setDecision(undefined);
    if (response.status === 409) {
      setMessage(
        "The job changed after your review. Review it again before publishing.",
      );
      setReviewed(false);
      return;
    }
    if (!response.ok) {
      setMessage("We couldn't update the public job page. Review it again.");
      return;
    }
    setPreview((await response.json()) as Publication);
    setReviewed(false);
    setMessage(
      decision === "publish"
        ? "Job published. The application link is ready to share."
        : "Job unpublished. Candidates can no longer open the public page.",
    );
  };
  return (
    <section
      className="fm12-publication"
      aria-label={`Publication for ${opening.title}`}
    >
      <div className="fm12-meta">
        <span>
          Job status:{" "}
          <strong>{preview?.internal_state ?? opening.state}</strong>
        </span>
        <span>
          Public page:{" "}
          <strong>{preview?.publication_state ?? "Loading"}</strong>
        </span>
      </div>
      {preview?.public_url && (
        <div className="fm12-share-actions">
          <a className="ui-button" href={preview.public_url} target="_blank">
            Open candidate page
          </a>
          <a
            className="ui-button"
            data-variant="secondary"
            href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(new URL(preview.public_url, location.origin).href)}`}
            target="_blank"
            rel="noreferrer"
          >
            <LinkedinLogo aria-hidden="true" /> Share on LinkedIn
          </a>
          <Button
            variant="secondary"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(
                  new URL(preview.public_url ?? "", location.origin).href,
                );
                setCopied(true);
              } catch {
                setCopied(false);
              }
            }}
          >
            <LinkSimple aria-hidden="true" />
            {copied ? "Candidate link copied" : "Copy candidate link"}
          </Button>
        </div>
      )}
      {reviewed && preview && (
        <dl className="fm12-preview">
          {Object.entries(preview.public_fields).map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>
                {value ||
                  (key === "published_at"
                    ? "Assigned when confirmed"
                    : "Not provided")}
              </dd>
            </div>
          ))}
        </dl>
      )}
      <div className="ui-row">
        <Button variant="secondary" onClick={() => void load(true)}>
          Review application page
        </Button>
        {preview?.internal_state === "DRAFT" ||
        preview?.internal_state === "PAUSED" ? (
          <Button variant="secondary" onClick={() => void changeState("OPEN")}>
            Mark ready to publish
          </Button>
        ) : null}
        {preview?.internal_state === "OPEN" && (
          <Button
            variant="secondary"
            onClick={() => void changeState("PAUSED")}
          >
            Pause applications
          </Button>
        )}
        <Button
          disabled={!reviewed || preview?.internal_state !== "OPEN"}
          onClick={() => setDecision("publish")}
        >
          {preview?.publication_state === "PUBLISHED"
            ? "Publish latest changes"
            : "Publish job"}
        </Button>
        <Button
          variant="danger"
          disabled={preview?.publication_state !== "PUBLISHED"}
          onClick={() => setDecision("withdraw")}
        >
          Unpublish job
        </Button>
      </div>
      <StatusMessage>{message}</StatusMessage>
      <Dialog
        open={Boolean(decision)}
        onClose={() => setDecision(undefined)}
        title={
          decision === "publish" ? "Publish this job?" : "Unpublish this job?"
        }
      >
        <p>
          {decision === "publish"
            ? "Candidates will be able to open this page and apply using the public link."
            : "Candidates will no longer be able to open this job page or submit new applications."}
        </p>
        <div className="ui-row">
          <Button
            variant={decision === "publish" ? "primary" : "danger"}
            onClick={() => void confirm()}
          >
            {decision === "publish" ? "Publish job" : "Unpublish job"}
          </Button>
          <Button variant="secondary" onClick={() => setDecision(undefined)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </section>
  );
}

function JobContentFields({ opening }: { opening?: Opening }) {
  return (
    <fieldset className="fm12-content-fields">
      <legend>Candidate-facing job page</legend>
      <p>
        These sections appear in this order when someone opens the LinkedIn job
        link.
      </p>
      <Field label="Company name">
        {(props) => (
          <TextInput
            {...props}
            name="company_name"
            required
            maxLength={300}
            defaultValue={opening?.company_name ?? ""}
          />
        )}
      </Field>
      <Field label="Job description">
        {(props) => (
          <Textarea
            {...props}
            name="description"
            required
            maxLength={20000}
            defaultValue={opening?.description ?? ""}
          />
        )}
      </Field>
      <Field label="About the company">
        {(props) => (
          <Textarea
            {...props}
            name="about_company"
            required
            maxLength={10000}
            defaultValue={opening?.about_company ?? ""}
          />
        )}
      </Field>
      <Field label="The role">
        {(props) => (
          <Textarea
            {...props}
            name="role_summary"
            required
            maxLength={10000}
            defaultValue={opening?.role_summary ?? ""}
          />
        )}
      </Field>
      <Field label="What you'll do">
        {(props) => (
          <Textarea
            {...props}
            name="responsibilities"
            required
            maxLength={20000}
            defaultValue={opening?.responsibilities ?? ""}
          />
        )}
      </Field>
      <Field label="What we're looking for">
        {(props) => (
          <Textarea
            {...props}
            name="requirements"
            required
            maxLength={20000}
            defaultValue={opening?.requirements ?? ""}
          />
        )}
      </Field>
      <Field label="Nice to have">
        {(props) => (
          <Textarea
            {...props}
            name="nice_to_have"
            maxLength={10000}
            defaultValue={opening?.nice_to_have ?? ""}
          />
        )}
      </Field>
    </fieldset>
  );
}

function JobActions({
  opening,
  base,
  request,
  reload,
}: {
  opening: Opening;
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [message, setMessage] = useState("");

  const currentEtag = async () => {
    const response = await request(`${base}/openings/${opening.id}`);
    if (!response.ok) return null;
    return response.headers.get("ETag");
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setMessage("Saving changes…");
    const etag = await currentEtag();
    if (!etag) {
      setMessage("We couldn't load the latest job. Refresh and try again.");
      return;
    }
    const response = await request(`${base}/openings/${opening.id}`, {
      method: "PATCH",
      headers: { ...jsonHeaders(), "If-Match": etag },
      body: JSON.stringify({
        title: data.get("title"),
        location: { display: data.get("location") },
        work_mode: data.get("work_mode"),
        employment_type: data.get("employment_type"),
        description: data.get("description"),
        company_name: data.get("company_name"),
        about_company: data.get("about_company"),
        role_summary: data.get("role_summary"),
        responsibilities: data.get("responsibilities"),
        requirements: data.get("requirements"),
        nice_to_have: data.get("nice_to_have"),
      }),
    });
    if (!response.ok) {
      setMessage(
        response.status === 409
          ? "This job changed in another session. Refresh and try again."
          : "We couldn't save these changes. Check the details and try again.",
      );
      return;
    }
    setEditing(false);
    setMessage(
      "Job updated. Review the application page before publishing it again.",
    );
    reload();
  };

  const remove = async () => {
    setMessage("Deleting job…");
    const etag = await currentEtag();
    if (!etag) {
      setConfirmDelete(false);
      setMessage("We couldn't load the latest job. Refresh and try again.");
      return;
    }
    const response = await request(`${base}/openings/${opening.id}`, {
      method: "DELETE",
      headers: { "If-Match": etag },
    });
    setConfirmDelete(false);
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as {
        opening?: string[] | string;
        detail?: string;
      };
      const reason = Array.isArray(payload.opening)
        ? payload.opening[0]
        : payload.opening || payload.detail;
      setMessage(
        reason ||
          "This job cannot be deleted. Unpublish it first and make sure it has no applicants.",
      );
      return;
    }
    setMessage("");
    reload();
  };

  return (
    <section
      className="fm12-job-actions"
      aria-label={`Manage ${opening.title}`}
    >
      <div className="ui-row">
        <Button variant="secondary" onClick={() => setEditing(true)}>
          Edit job
        </Button>
        <Button variant="danger" onClick={() => setConfirmDelete(true)}>
          Delete job
        </Button>
      </div>
      <StatusMessage>{message}</StatusMessage>
      <Dialog
        open={editing}
        onClose={() => setEditing(false)}
        title={`Edit ${opening.title}`}
      >
        <p>
          Update the information candidates will see. Saving changes to a
          published job unpublishes it until you review and publish it again.
        </p>
        <form
          className="fm12-form fm12-edit-job-form"
          onSubmit={(event) => void save(event)}
        >
          <Field label="Job title">
            {(props) => (
              <TextInput
                {...props}
                name="title"
                required
                maxLength={300}
                defaultValue={opening.title}
              />
            )}
          </Field>
          <Field label="Job location">
            {(props) => (
              <TextInput
                {...props}
                name="location"
                required
                defaultValue={opening.location.display ?? ""}
              />
            )}
          </Field>
          <Field label="Where will they work?">
            {(props) => (
              <Select
                {...props}
                name="work_mode"
                defaultValue={opening.work_mode}
              >
                <option value="REMOTE">Remote</option>
                <option value="HYBRID">Hybrid</option>
                <option value="ON_SITE">On-site</option>
                <option value="FLEXIBLE">Flexible</option>
              </Select>
            )}
          </Field>
          <Field label="Employment type">
            {(props) => (
              <Select
                {...props}
                name="employment_type"
                defaultValue={opening.employment_type}
              >
                <option value="PERMANENT">Permanent</option>
                <option value="CONTRACT">Contract</option>
                <option value="PART_TIME">Part-time</option>
                <option value="INTERNSHIP">Internship</option>
              </Select>
            )}
          </Field>
          <JobContentFields opening={opening} />
          <div className="ui-row">
            <Button type="submit">Save changes</Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      </Dialog>
      <Dialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        title={`Delete ${opening.title}?`}
      >
        <p>
          This permanently removes the job. A published job must be unpublished
          first, and a job with applicants cannot be deleted.
        </p>
        <div className="ui-row">
          <Button variant="danger" onClick={() => void remove()}>
            Delete job permanently
          </Button>
          <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
            Keep job
          </Button>
        </div>
      </Dialog>
    </section>
  );
}

function ApplicantPanel({
  opening,
  base,
  request,
}: {
  opening: Opening;
  base: string;
  request: Request;
}) {
  const [items, setItems] = useState<Applicant[] | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    setLoading(true);
    const response = await request(
      `${base}/openings/${opening.id}/applications`,
    );
    if (!response.ok) {
      setMessage("Applicants are unavailable. Your access may have changed.");
      setLoading(false);
      return;
    }
    setItems((await response.json()) as Applicant[]);
    setMessage("");
    setLoading(false);
  }, [base, opening.id, request]);
  useEffect(() => void load(), [load]);
  const updateStatus = async (item: Applicant, internal_status: string) => {
    const response = await request(
      `${base}/applications/${item.id}/internal-status`,
      {
        method: "PUT",
        headers: { ...jsonHeaders(), "If-Match": item.etag },
        body: JSON.stringify({ internal_status }),
      },
    );
    if (!response.ok) {
      setMessage("Status was not saved. Refresh applicants and try again.");
      return;
    }
    const next = (await response.json()) as {
      internal_status: string;
      version: number;
    };
    setItems(
      (current) =>
        current?.map((candidate) =>
          candidate.id === item.id
            ? {
                ...candidate,
                internal_status: next.internal_status,
                version: next.version,
                etag: response.headers.get("ETag") ?? candidate.etag,
              }
            : candidate,
        ) ?? current,
    );
    setMessage("Recruiter status saved.");
  };
  return (
    <section
      className="fm12-applicants"
      aria-label={`Applicants for ${opening.title}`}
    >
      <div className="fm12-meta">
        <h4>Applicants {items ? `(${items.length})` : ""}</h4>
        <Button variant="secondary" busy={loading} onClick={() => void load()}>
          Refresh applicants
        </Button>
      </div>
      {message && <StatusMessage>{message}</StatusMessage>}
      {items?.length === 0 && <p>No applications yet.</p>}
      {items && items.length > 0 && (
        <div className="fm12-applicant-list">
          {items.map((item) => (
            <article className="fm12-applicant" key={item.id}>
              <div className="fm12-card-head">
                <div>
                  <h5>{item.name || "Candidate"}</h5>
                  <p>
                    {item.current_role || item.headline || "Candidate profile"}
                    {item.current_company ? ` at ${item.current_company}` : ""}
                  </p>
                </div>
                <Chip tone="sage">{item.candidate_status.toLowerCase()}</Chip>
              </div>
              <p className="ui-help">
                {item.experience_years ?? "—"} years experience · submitted{" "}
                {new Date(item.submitted_at).toLocaleDateString()}
              </p>
              <div className="ui-row">
                <label>
                  Recruiter status
                  <select
                    value={item.internal_status || "SOURCED"}
                    onChange={(event) =>
                      void updateStatus(item, event.target.value)
                    }
                  >
                    {[
                      "SOURCED",
                      "SHORTLISTED",
                      "CONTACTED",
                      "SCREENING",
                      "INTERVIEWING",
                      "OFFERED",
                      "REJECTED",
                      "HIRED",
                    ].map((status) => (
                      <option key={status} value={status}>
                        {status.toLowerCase().replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
                {item.resume_available && (
                  <a
                    className="ui-button ui-button-secondary"
                    href={item.resume_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View resume
                  </a>
                )}
              </div>
              <details>
                <summary>View profile</summary>
                <dl className="fm12-applicant-details">
                  <div>
                    <dt>Location</dt>
                    <dd>{item.location?.display || "Not provided"}</dd>
                  </div>
                  <div>
                    <dt>Skills</dt>
                    <dd>
                      {item.skills.length
                        ? item.skills.join(", ")
                        : "Not provided"}
                    </dd>
                  </div>
                  <div>
                    <dt>Education</dt>
                    <dd>
                      {item.education.length
                        ? item.education
                            .map((record) =>
                              String(
                                record.school ||
                                  record.institution ||
                                  "Education",
                              ),
                            )
                            .join(", ")
                        : "Not provided"}
                    </dd>
                  </div>
                  <div>
                    <dt>Career history</dt>
                    <dd>
                      {item.employment_history.length
                        ? item.employment_history
                            .map(
                              (record) =>
                                `${String(record.role_title || "Role")} at ${String(record.company || "Company")}`,
                            )
                            .join(" · ")
                        : "Not provided"}
                    </dd>
                  </div>
                  <div>
                    <dt>Links</dt>
                    <dd>
                      {item.professional_links.length
                        ? item.professional_links.map((url) => (
                            <a
                              key={url}
                              href={url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {url}
                            </a>
                          ))
                        : "Not provided"}
                    </dd>
                  </div>
                  {item.motivation && (
                    <div>
                      <dt>Motivation</dt>
                      <dd>{item.motivation}</dd>
                    </div>
                  )}
                </dl>
              </details>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function OpeningEditor({
  openings,
  units,
  base,
  request,
  reload,
  canCreate,
  canReviewApplicants,
}: {
  openings: Opening[];
  units: Unit[];
  base: string;
  request: Request;
  reload: () => void;
  canCreate: boolean;
  canReviewApplicants: boolean;
}) {
  const [message, setMessage] = useState("");
  const [jobQuery, setJobQuery] = useState("");
  const [stateFilter, setStateFilter] = useState<"ALL" | Opening["state"]>(
    "ALL",
  );
  const [visibleJobCount, setVisibleJobCount] = useState(6);
  const filteredOpenings = openings.filter((opening) => {
    const matchesQuery = opening.title
      .toLocaleLowerCase()
      .includes(jobQuery.trim().toLocaleLowerCase());
    const matchesState = stateFilter === "ALL" || opening.state === stateFilter;
    return matchesQuery && matchesState;
  });
  const visibleOpenings = canCreate
    ? filteredOpenings.slice(0, visibleJobCount)
    : filteredOpenings;
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setMessage("Creating job…");
    let unit = units.find((item) => item.status === "ACTIVE");
    if (!unit) {
      const unitResponse = await request(`${base}/business-units`, {
        method: "POST",
        headers: jsonHeaders(),
        body: JSON.stringify({
          name: "General",
          description: "Default team for published jobs",
        }),
      });
      if (!unitResponse.ok) {
        setMessage("We couldn't prepare this job. Please try again.");
        return;
      }
      unit = (await unitResponse.json()) as Unit;
    }
    const response = await request(`${base}/openings`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        business_unit_id: unit.id,
        title: data.get("title"),
        description: data.get("description"),
        location: { display: data.get("location") },
        work_mode: data.get("work_mode"),
        employment_type: data.get("employment_type"),
        company_name: data.get("company_name"),
        about_company: data.get("about_company"),
        role_summary: data.get("role_summary"),
        responsibilities: data.get("responsibilities"),
        requirements: data.get("requirements"),
        nice_to_have: data.get("nice_to_have"),
      }),
    });
    setMessage(
      response.ok
        ? "Job saved as a draft. Review it below when you are ready to publish."
        : "We couldn't create this job. Check the details and try again.",
    );
    if (response.ok) {
      form.reset();
      reload();
    }
  };
  return (
    <Card title={canCreate ? "Create and publish jobs" : "Jobs and applicants"}>
      <p>
        {canCreate
          ? "Add the job details. Save it, review the public page and publish the link when it is ready."
          : "Admins publish jobs. Review the people who applied and move the best candidates forward."}
      </p>
      {canCreate && (
        <form
          className="fm12-form fm12-form-grid fm12-job-form"
          onSubmit={(e) => void submit(e)}
        >
          <Field label="Job title">
            {(props) => (
              <TextInput {...props} name="title" required maxLength={300} />
            )}
          </Field>
          <Field label="Job location">
            {(props) => <TextInput {...props} name="location" required />}
          </Field>
          <Field label="Where will they work?">
            {(props) => (
              <Select {...props} name="work_mode">
                <option value="REMOTE">Remote</option>
                <option value="HYBRID">Hybrid</option>
                <option value="ON_SITE">On-site</option>
                <option value="FLEXIBLE">Flexible</option>
              </Select>
            )}
          </Field>
          <Field label="Employment type">
            {(props) => (
              <Select
                {...props}
                name="employment_type"
                defaultValue="PERMANENT"
              >
                <option value="PERMANENT">Permanent</option>
                <option value="CONTRACT">Contract</option>
                <option value="PART_TIME">Part-time</option>
                <option value="INTERNSHIP">Internship</option>
              </Select>
            )}
          </Field>
          <JobContentFields />
          <Button type="submit">Save job as draft</Button>
        </form>
      )}
      <StatusMessage>{message}</StatusMessage>
      {openings.length > 0 && (
        <section
          className="fm12-job-library"
          aria-labelledby="fm12-job-list-title"
        >
          <div className="fm12-job-library-head">
            <div>
              <h3 id="fm12-job-list-title">Your jobs</h3>
              <p>
                {canCreate
                  ? "Review, publish or pause a job. Recent jobs appear first."
                  : "Choose a job to review its applicants."}
              </p>
            </div>
            <strong className="fm12-job-count">
              {filteredOpenings.length}{" "}
              {filteredOpenings.length === 1 ? "job" : "jobs"}
            </strong>
          </div>
          <div className="fm12-job-toolbar">
            <Field label="Find a job">
              {(props) => (
                <TextInput
                  {...props}
                  type="search"
                  value={jobQuery}
                  placeholder="Search by job title"
                  onChange={(event) => {
                    setJobQuery(event.target.value);
                    setVisibleJobCount(6);
                  }}
                />
              )}
            </Field>
            <Field label="Status">
              {(props) => (
                <Select
                  {...props}
                  value={stateFilter}
                  onChange={(event) => {
                    setStateFilter(
                      event.target.value as "ALL" | Opening["state"],
                    );
                    setVisibleJobCount(6);
                  }}
                >
                  <option value="ALL">All statuses</option>
                  <option value="DRAFT">Draft</option>
                  <option value="OPEN">Open</option>
                  <option value="PAUSED">Paused</option>
                  <option value="CLOSED">Closed</option>
                </Select>
              )}
            </Field>
          </div>
        </section>
      )}
      <div className="fm12-opening-list">
        {visibleOpenings.map((opening) => (
          <article className="fm12-opening" key={opening.id}>
            <div className="fm12-card-head">
              <div>
                <p className="fm12-kicker">
                  {canCreate
                    ? "Job"
                    : (units.find((u) => u.id === opening.business_unit_id)
                        ?.name ?? "Hiring team")}
                </p>
                <h3>{opening.title}</h3>
              </div>
              <Chip tone={opening.state === "OPEN" ? "sage" : "gold"}>
                {opening.state.toLowerCase()}
              </Chip>
            </div>
            <p>{opening.description || "No internal description"}</p>
            {canCreate && (
              <>
                <JobActions
                  opening={opening}
                  base={base}
                  request={request}
                  reload={reload}
                />
                <PublicationPanel
                  opening={opening}
                  base={base}
                  request={request}
                  reload={reload}
                />
              </>
            )}
            {canReviewApplicants && (
              <ApplicantPanel opening={opening} base={base} request={request} />
            )}
          </article>
        ))}
      </div>
      {filteredOpenings.length > visibleOpenings.length && canCreate && (
        <div className="fm12-job-list-footer">
          <p>
            Showing {visibleOpenings.length} of {filteredOpenings.length} jobs
          </p>
          <Button
            variant="secondary"
            onClick={() => setVisibleJobCount((count) => count + 6)}
          >
            Show 6 more
          </Button>
        </div>
      )}
      {openings.length > 0 && filteredOpenings.length === 0 && (
        <p className="fm12-no-jobs">
          No jobs match that search. Try a different title or status.
        </p>
      )}
      {openings.length === 0 && (
        <p>{canCreate ? "No jobs yet." : "No jobs are available yet."}</p>
      )}
    </Card>
  );
}

export function SyntheticCandidatePanel({
  items,
  base,
  request,
  reload,
}: {
  items: Synthetic[];
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = await request(`${base}/recruiter-entered-candidates`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        display_name: data.get("display_name"),
        location: { display: data.get("location") },
        experience_years: data.get("experience_years"),
        skills: String(data.get("skills") ?? "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        confirm_synthetic: confirmed,
      }),
    });
    setMessage(
      response.ok
        ? "Synthetic candidate created with immutable provenance."
        : "Synthetic candidate was not created.",
    );
    if (response.ok) {
      form.reset();
      setConfirmed(false);
      reload();
    }
  };
  return (
    <Card title="Synthetic candidate fixtures">
      <Alert tone="gold">
        <strong>Test data only.</strong> These records cannot contain real
        candidate details, contact information or resumes, and never merge with
        candidate-controlled profiles.
      </Alert>
      <form
        className="fm12-form fm12-form-grid"
        onSubmit={(e) => void submit(e)}
      >
        <Field label="Synthetic display name">
          {(props) => <TextInput {...props} name="display_name" required />}
        </Field>
        <Field label="Synthetic location">
          {(props) => <TextInput {...props} name="location" required />}
        </Field>
        <Field label="Experience years">
          {(props) => (
            <TextInput
              {...props}
              name="experience_years"
              type="number"
              min="0"
              step="0.01"
              required
            />
          )}
        </Field>
        <Field label="Synthetic skills" help="Separate skills with commas.">
          {(props) => <TextInput {...props} name="skills" required />}
        </Field>
        <Checkbox
          label="I confirm this is entirely synthetic test data."
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
          required
        />
        <Button type="submit" disabled={!confirmed}>
          Create synthetic candidate
        </Button>
      </form>
      <StatusMessage>{message}</StatusMessage>
      <ul className="fm12-list">
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.display_name}</strong>
            <p>{item.source_label}</p>
            <p>{item.skills.join(", ")}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function SavedSearchManager({
  items,
  base,
  request,
  reload,
}: {
  items: Saved[];
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = await request(`${base}/saved-searches`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        name: data.get("name"),
        search_id: data.get("search_id"),
      }),
    });
    setMessage(
      response.ok
        ? "Search saved from its authoritative criteria context."
        : "Search was not saved.",
    );
    if (response.ok) {
      form.reset();
      reload();
    }
  };
  return (
    <Card title="Saved searches">
      <p>
        Opening context comes only from the selected search definition. It
        cannot be supplied independently here.
      </p>
      <form className="fm12-form" onSubmit={(e) => void submit(e)}>
        <Field label="Saved-search name">
          {(props) => (
            <TextInput {...props} name="name" required maxLength={200} />
          )}
        </Field>
        <Field label="Owned search ID">
          {(props) => <TextInput {...props} name="search_id" required />}
        </Field>
        <Button type="submit">Save search</Button>
      </form>
      <StatusMessage>{message}</StatusMessage>
      <ul className="fm12-list">
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.name}</strong>
            <p>
              {item.criteria.context.type}
              {item.criteria.context.opening_id
                ? ` · opening ${item.criteria.context.opening_id}`
                : ""}
            </p>
            {item.changed_since_save.length > 0 && (
              <Alert tone="gold">
                Changed since save: {item.changed_since_save.join(", ")}
              </Alert>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function OrganizationPage({ bootstrap, request }: PageProps) {
  const tenantId = bootstrap.tenantId ?? "";
  const base = `/api/v1/tenants/${tenantId}`;
  const isAdmin = bootstrap.role === "TENANT_ADMIN";
  const [units, setUnits] = useState<Unit[]>([]);
  const [openings, setOpenings] = useState<Opening[]>([]);
  const [synthetic, setSynthetic] = useState<Synthetic[]>([]);
  const [saved, setSaved] = useState<Saved[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    setFailed(false);
    try {
      const paths = isAdmin
        ? ["business-units", "openings"]
        : [
            "business-units",
            "openings",
            "recruiter-entered-candidates",
            "saved-searches",
          ];
      const responses = await Promise.all(
        paths.map((path) => request(`${base}/${path}`)),
      );
      if (responses.some((response) => !response.ok)) throw new Error();
      const [nextUnits, nextOpenings, nextSynthetic = [], nextSaved = []] =
        await Promise.all(responses.map((response) => response.json()));
      setUnits(nextUnits as Unit[]);
      setOpenings(nextOpenings as Opening[]);
      setSynthetic(nextSynthetic as Synthetic[]);
      setSaved(nextSaved as Saved[]);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [base, isAdmin, request]);
  useEffect(() => void load(), [load]);
  const navigation = isAdmin ? (
    <WorkspaceNavigation
      label="Admin navigation"
      items={[
        {
          label: "Manage jobs",
          href: `/tenants/${tenantId}/admin/jobs/`,
          current: true,
        },
      ]}
    />
  ) : (
    <WorkspaceNavigation
      label="Recruiter navigation"
      items={[
        { label: "Search", href: `/tenants/${tenantId}/recruiter/search/` },
        {
          label: "Organization",
          href: `/tenants/${tenantId}/recruiter/organization/`,
          current: true,
        },
      ]}
    />
  );
  return (
    <AppShell
      title={isAdmin ? "Manage jobs" : "Recruiter workspace"}
      navigation={navigation}
    >
      <p>
        {isAdmin
          ? "Create a job, check what candidates will see and publish the application link."
          : "Review openings, search candidates and manage applicants inside the current tenant."}
      </p>
      {loading && (
        <Loading label={isAdmin ? "Loading jobs…" : "Loading workspace…"} />
      )}
      {failed && <ErrorState onRetry={() => void load()} />}
      {!loading && !failed && (
        <div className={`fm12-grid${isAdmin ? " fm12-grid-admin" : ""}`}>
          <OpeningEditor
            openings={openings}
            units={units}
            base={base}
            request={request}
            reload={() => void load()}
            canCreate={isAdmin}
            canReviewApplicants={!isAdmin}
          />
          {!isAdmin && (
            <>
              <SyntheticCandidatePanel
                items={synthetic}
                base={base}
                request={request}
                reload={() => void load()}
              />
              <SavedSearchManager
                items={saved}
                base={base}
                request={request}
                reload={() => void load()}
              />
            </>
          )}
        </div>
      )}
      {!loading &&
        !failed &&
        !units.length &&
        !openings.length &&
        !synthetic.length &&
        !saved.length && (
          <EmptyState
            title="Organization is ready"
            illustration={{
              src: visualAssets.organizationSetupEmpty,
              width: 1024,
              height: 1024,
            }}
          >
            {isAdmin
              ? "Create a business unit to begin."
              : "An administrator must publish a role before recruiting begins."}
          </EmptyState>
        )}
    </AppShell>
  );
}
