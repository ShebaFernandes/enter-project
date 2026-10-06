import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { LinkedinLogo } from "@phosphor-icons/react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Container,
  EmptyState,
  Field,
  Header,
  Loading,
  SkipLink,
  StatusMessage,
  Textarea,
} from "./components";
import type { PageProps } from "./mount";
import { visualAssets } from "./visual-assets";
import { ResumeUploader } from "./candidate-profile";

type Opening = {
  id: string;
  title: string;
  description: string;
  location: string;
  work_mode: string;
  employment_type: string;
  published_at: string;
  closes_at: string | null;
  application_url: string;
  company_name: string;
  about_company: string;
  role_summary: string;
  responsibilities: string;
  requirements: string;
  nice_to_have: string;
};

type Directory = { items: Opening[]; next_cursor: string | null };
type Readiness = {
  profile_name: string;
  profile_state: string;
  resume: {
    id: string;
    scan_status: string;
    parse_status: string;
    ready: boolean;
  } | null;
  already_applied: boolean;
  application_id: string | null;
};

const humanize = (value: string) =>
  value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());

function PublicHeader({
  applicationFlow = false,
}: {
  applicationFlow?: boolean;
}) {
  return (
    <Header>
      <nav className="fm10-nav" aria-label="Public navigation">
        {applicationFlow ? (
          <>
            <a href="/candidate/profile/">My resume</a>
            <a href="/candidate/applications/">My applications</a>
          </>
        ) : (
          <>
            <a href="/jobs/" aria-current="page">
              Open roles
            </a>
            <a href="/candidate/profile/">Candidate account</a>
          </>
        )}
      </nav>
    </Header>
  );
}

export function JobCard({ opening }: { opening: Opening }) {
  const shareUrl = new URL(opening.application_url, location.origin).href;
  return (
    <article className="fm10-job-card">
      <div className="fm10-card-heading">
        <p className="fm10-kicker">Open role</p>
        <h2>{opening.title}</h2>
        {opening.company_name && <span>{opening.company_name}</span>}
      </div>
      <p>{opening.description}</p>
      <dl className="fm10-essentials">
        <div>
          <dt>Location</dt>
          <dd>{opening.location || "Not specified"}</dd>
        </div>
        <div>
          <dt>Work arrangement</dt>
          <dd>{humanize(opening.work_mode)}</dd>
        </div>
        <div>
          <dt>Employment type</dt>
          <dd>{humanize(opening.employment_type)}</dd>
        </div>
      </dl>
      <div className="fm10-card-actions">
        <a className="ui-button fm10-card-link" href={opening.application_url}>
          View {opening.title}
        </a>
        <a
          className="fm10-share-link"
          href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`}
          target="_blank"
          rel="noreferrer"
          aria-label={`Share ${opening.title} on LinkedIn`}
        >
          <LinkedinLogo aria-hidden="true" /> Share
        </a>
      </div>
    </article>
  );
}

function JobSection({ title, content }: { title: string; content: string }) {
  if (!content.trim()) return null;
  return (
    <section
      className="fm10-description"
      aria-labelledby={`job-${title.toLowerCase().replaceAll(/[^a-z]+/g, "-")}`}
    >
      <h2 id={`job-${title.toLowerCase().replaceAll(/[^a-z]+/g, "-")}`}>
        {title}
      </h2>
      <p>{content}</p>
    </section>
  );
}

export function JobsDirectory({ request }: PageProps) {
  const [directory, setDirectory] = useState<Directory>();
  const [failed, setFailed] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(
    async (cursor?: string) => {
      if (cursor) setLoadingMore(true);
      else setFailed(false);
      try {
        const url = `/api/v1/public/openings?limit=25${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`;
        const response = await request(url);
        if (!response.ok) throw new Error("directory unavailable");
        const next = (await response.json()) as Directory;
        setDirectory((current) =>
          cursor && current
            ? {
                items: [...current.items, ...next.items],
                next_cursor: next.next_cursor,
              }
            : next,
        );
      } catch {
        setFailed(true);
      } finally {
        setLoadingMore(false);
      }
    },
    [request],
  );

  useEffect(() => void load(), [load]);

  return (
    <div className="ui-shell fm10-shell">
      <SkipLink />
      <PublicHeader />
      <main id="main" tabIndex={-1}>
        <Container width="public">
          <section className="fm10-hero" aria-labelledby="jobs-title">
            <div className="fm10-hero-copy">
              <p className="fm10-kicker">Candidate opportunities</p>
              <h1 id="jobs-title">Find work that matters</h1>
              <p>
                Explore currently published roles. You stay in control of your
                profile, consent and application updates.
              </p>
            </div>
            <img
              className="fm10-hero-illustration"
              src={visualAssets.jobsOpportunitiesHero}
              width={1536}
              height={1024}
              alt=""
              aria-hidden="true"
              loading="eager"
              decoding="async"
              fetchPriority="high"
            />
          </section>
          {failed && (
            <div className="ui-stack">
              <Alert>
                Public roles are temporarily unavailable. No application has
                changed.
              </Alert>
              <Button variant="secondary" onClick={() => void load()}>
                Try again
              </Button>
            </div>
          )}
          {!failed && !directory && <Loading label="Loading open roles…" />}
          {!failed && directory?.items.length === 0 && (
            <EmptyState
              title="No open roles right now"
              illustration={{
                src: visualAssets.openRolesEmpty,
                width: 1024,
                height: 1024,
              }}
            >
              Published roles will appear here when they are available. Please
              check again later.
            </EmptyState>
          )}
          {!failed && Boolean(directory?.items.length) && (
            <section className="fm10-job-grid" aria-label="Open roles">
              {directory?.items.map((opening) => (
                <JobCard key={opening.id} opening={opening} />
              ))}
            </section>
          )}
          {directory?.next_cursor && (
            <div className="fm10-more">
              <Button
                variant="secondary"
                busy={loadingMore}
                onClick={() => void load(directory.next_cursor ?? undefined)}
              >
                {loadingMore ? "Loading more roles…" : "Load more roles"}
              </Button>
            </div>
          )}
        </Container>
      </main>
    </div>
  );
}

function ChannelPreferences({
  email,
  whatsapp,
  onEmail,
  onWhatsapp,
}: {
  email: boolean;
  whatsapp: boolean;
  onEmail: (checked: boolean) => void;
  onWhatsapp: (checked: boolean) => void;
}) {
  return (
    <fieldset className="fm10-channels">
      <legend>Status update channels</legend>
      <Checkbox
        label="Email"
        checked={email}
        onChange={(event) => onEmail(event.target.checked)}
      />
      <Checkbox
        label="WhatsApp"
        checked={whatsapp}
        onChange={(event) => onWhatsapp(event.target.checked)}
      />
    </fieldset>
  );
}

function RoleResumeUploader({ request }: { request: PageProps["request"] }) {
  return (
    <ResumeUploader
      request={request}
      disabled={false}
      onReady={() => undefined}
      onApplySuggestions={(_suggestions, _fillMissing, resumeId) => {
        if (!resumeId) return;
        const reviewUrl = new URL("/candidate/profile/", location.origin);
        reviewUrl.searchParams.set("return_to", location.pathname);
        reviewUrl.searchParams.set("resume_id", resumeId);
        location.assign(reviewUrl.href);
      }}
    />
  );
}

function ApplicationForm({
  openingId,
  readiness,
  request,
  onSubmitted,
}: {
  openingId: string;
  readiness: Readiness;
  request: PageProps["request"];
  onSubmitted: () => void;
}) {
  const [motivation, setMotivation] = useState("");
  const [emailUpdates, setEmailUpdates] = useState(false);
  const [whatsappUpdates, setWhatsappUpdates] = useState(false);
  const [consented, setConsented] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const form = useRef<HTMLFormElement>(null);
  const ready = Boolean(readiness.resume?.ready);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.current?.reportValidity()) return;
    if (!ready) {
      setMessage(
        "Finish reviewing your clean resume before applying. Your answer remains on this page.",
      );
      return;
    }
    setBusy(true);
    setMessage("Submitting application…");
    try {
      const preparation = await request(
        "/api/v1/candidate/applications/prepare",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({ opening_id: openingId, confirmed: consented }),
        },
      );
      if (preparation.status === 409) {
        setMessage(
          "You already applied to this role. No duplicate application was created.",
        );
        onSubmitted();
        return;
      }
      if (!preparation.ok) {
        setMessage(
          preparation.status === 401 || preparation.status === 403
            ? "Your candidate session is unavailable. Sign in again; no application was submitted."
            : "Your resume or consent is not ready. Review your candidate profile and try again.",
        );
        return;
      }
      const prepared = (await preparation.json()) as {
        resume_id: string;
        consent_record_id: string;
      };
      const response = await request("/api/v1/candidate/applications", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          opening_id: openingId,
          resume_id: prepared.resume_id,
          answers: { motivation },
          consent_record_id: prepared.consent_record_id,
          notification_preferences: {
            email: emailUpdates,
            whatsapp: whatsappUpdates,
          },
        }),
      });
      if (!response.ok) {
        setMessage(
          response.status === 409
            ? "You already applied to this role. No duplicate application was created."
            : response.status === 401 || response.status === 403
              ? "Your candidate session or consent is unavailable. Sign in again; no application was submitted."
              : "Application could not be submitted. Your details remain on this page; try again safely.",
        );
        return;
      }
      setMessage("Application submitted. Your candidate status is Applied.");
      setMotivation("");
      setConsented(false);
      onSubmitted();
    } catch {
      setMessage(
        "Application could not be submitted. Your details remain on this page; try again safely.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Quick application">
      <form
        ref={form}
        className="fm10-application-form"
        onSubmit={submit}
        noValidate
      >
        <p className="fm10-verified-candidate">
          Applying as{" "}
          <strong>{readiness.profile_name || "verified candidate"}</strong>
        </p>
        <Field label="Why are you interested?">
          {(props) => (
            <Textarea
              {...props}
              value={motivation}
              onChange={(event) => setMotivation(event.target.value)}
            />
          )}
        </Field>
        <section className="fm10-resume" aria-labelledby="resume-title">
          <h3 id="resume-title">Resume</h3>
          <p>
            Your current resume is ready. You can use it now or upload a newer
            resume before applying.
          </p>
        </section>
        <RoleResumeUploader request={request} />
        <ChannelPreferences
          email={emailUpdates}
          whatsapp={whatsappUpdates}
          onEmail={setEmailUpdates}
          onWhatsapp={setWhatsappUpdates}
        />
        <Checkbox
          label="I consent to use of my profile and clean resume for this application."
          required
          checked={consented}
          onChange={(event) => setConsented(event.target.checked)}
        />
        <Button type="submit" busy={busy}>
          {busy ? "Submitting…" : "Apply"}
        </Button>
        <StatusMessage>{message}</StatusMessage>
      </form>
    </Card>
  );
}

export function RolePage({ bootstrap, request }: PageProps) {
  const [opening, setOpening] = useState<Opening>();
  const [failed, setFailed] = useState(false);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [candidateState, setCandidateState] = useState<
    "checking" | "anonymous" | "authenticated" | "failed"
  >("checking");
  const openingId = bootstrap.openingId ?? "";

  const load = useCallback(async () => {
    setFailed(false);
    try {
      const response = await request(`/api/v1/public/openings/${openingId}`);
      if (!response.ok) throw new Error("role unavailable");
      setOpening((await response.json()) as Opening);
    } catch {
      setFailed(true);
      setOpening(undefined);
    }
  }, [openingId, request]);

  useEffect(() => void load(), [load]);

  const loadReadiness = useCallback(async () => {
    setCandidateState("checking");
    try {
      const response = await request(
        `/api/v1/candidate/applications/readiness?opening_id=${encodeURIComponent(openingId)}`,
      );
      if ([401, 403, 404].includes(response.status)) {
        setReadiness(null);
        setCandidateState("anonymous");
        return;
      }
      if (!response.ok) throw new Error("readiness unavailable");
      setReadiness((await response.json()) as Readiness);
      setCandidateState("authenticated");
    } catch {
      setReadiness(null);
      setCandidateState("failed");
    }
  }, [openingId, request]);

  useEffect(() => void loadReadiness(), [loadReadiness]);

  return (
    <div className="ui-shell fm10-shell">
      <SkipLink />
      <PublicHeader applicationFlow />
      <main id="main" tabIndex={-1}>
        <Container width="public">
          {failed && (
            <EmptyState
              title="This role is unavailable"
              action={<a href="/">Return home</a>}
            >
              It may have closed or paused. No application has been changed.
            </EmptyState>
          )}
          {!failed && !opening && <Loading label="Loading role…" />}
          {opening && (
            <div className="fm10-role-layout">
              <section className="fm10-role-copy" aria-labelledby="role-title">
                <p className="fm10-kicker">Open role</p>
                <h1 id="role-title">{opening.title}</h1>
                {opening.company_name && (
                  <p className="fm10-company-name">{opening.company_name}</p>
                )}
                <dl className="fm10-essentials">
                  <div>
                    <dt>Location</dt>
                    <dd>{opening.location || "Not specified"}</dd>
                  </div>
                  <div>
                    <dt>Work arrangement</dt>
                    <dd>{humanize(opening.work_mode)}</dd>
                  </div>
                  <div>
                    <dt>Employment type</dt>
                    <dd>{humanize(opening.employment_type)}</dd>
                  </div>
                </dl>
                <JobSection
                  title="Job description"
                  content={opening.description}
                />
                <JobSection
                  title="About the company"
                  content={opening.about_company}
                />
                <JobSection title="The role" content={opening.role_summary} />
                <JobSection
                  title="What you'll do"
                  content={opening.responsibilities}
                />
                <JobSection
                  title="What we're looking for"
                  content={opening.requirements}
                />
                <JobSection
                  title="Nice to have"
                  content={opening.nice_to_have}
                />
                <section
                  className="fm10-description"
                  aria-labelledby="next-title"
                >
                  <h2 id="next-title">What happens next</h2>
                  <p>
                    Your application is stored separately for this role. You
                    control withdrawal and update channels, and no automated
                    hiring decision is made.
                  </p>
                </section>
              </section>
              {candidateState === "checking" && (
                <Card title="Apply for this role">
                  <Loading label="Checking your candidate profile…" />
                </Card>
              )}
              {candidateState === "anonymous" && (
                <Card title="Apply for this role">
                  <div className="fm10-entry-card">
                    <p>
                      Sign in with a verified email, add your resume and apply.
                      Your profile stays under your control.
                    </p>
                    <a
                      className="ui-button"
                      href={`/api/v1/auth/login?platform=candidate&return_to=${encodeURIComponent(location.pathname)}`}
                    >
                      Sign in to apply
                    </a>
                    <small>
                      Usually takes 3–5 minutes with a prepared resume.
                    </small>
                  </div>
                </Card>
              )}
              {candidateState === "failed" && (
                <Card title="Apply for this role">
                  <Alert>
                    We couldn’t check your candidate profile. No application was
                    changed.
                  </Alert>
                  <Button
                    variant="secondary"
                    onClick={() => void loadReadiness()}
                  >
                    Try again
                  </Button>
                </Card>
              )}
              {candidateState === "authenticated" &&
                readiness?.already_applied && (
                  <Card title="Application received">
                    <p>You already applied to this role.</p>
                    <a className="ui-button" href="/candidate/applications/">
                      Track application
                    </a>
                  </Card>
                )}
              {candidateState === "authenticated" &&
                readiness &&
                !readiness.already_applied &&
                !readiness.resume?.ready && (
                  <Card title="Drop your resume to apply">
                    <p>
                      Upload a PDF or Word resume. We’ll scan it, extract the
                      details and ask you to review them before applying.
                    </p>
                    <RoleResumeUploader request={request} />
                    <a
                      className="fm10-manual-profile-link"
                      href={`/candidate/profile/?return_to=${encodeURIComponent(location.pathname)}`}
                    >
                      Enter details without uploading
                    </a>
                  </Card>
                )}
              {candidateState === "authenticated" &&
                readiness &&
                !readiness.already_applied &&
                readiness.resume?.ready && (
                  <ApplicationForm
                    openingId={opening.id}
                    readiness={readiness}
                    request={request}
                    onSubmitted={() => void loadReadiness()}
                  />
                )}
            </div>
          )}
        </Container>
      </main>
    </div>
  );
}
