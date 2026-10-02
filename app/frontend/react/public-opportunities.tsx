import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
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
  TextInput,
} from "./components";
import type { PageProps } from "./mount";

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
};

type Directory = { items: Opening[]; next_cursor: string | null };

const humanize = (value: string) =>
  value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());

function PublicHeader() {
  return (
    <Header>
      <nav className="fm10-nav" aria-label="Public navigation">
        <a href="/jobs/" aria-current="page">
          Open roles
        </a>
        <a href="/candidate/profile/">Candidate profile</a>
      </nav>
    </Header>
  );
}

export function JobCard({ opening }: { opening: Opening }) {
  return (
    <article className="fm10-job-card">
      <div className="fm10-card-heading">
        <p className="fm10-kicker">Open role</p>
        <h2>{opening.title}</h2>
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
      <a className="ui-button fm10-card-link" href={opening.application_url}>
        View {opening.title}
      </a>
    </article>
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
            <p className="fm10-kicker">Candidate opportunities</p>
            <h1 id="jobs-title">Find work that matters</h1>
            <p>
              Explore currently published roles. You stay in control of your
              profile, consent and application updates.
            </p>
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
            <EmptyState title="No open roles right now">
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

function ResumeConsent({ available }: { available: boolean }) {
  return (
    <section className="fm10-resume" aria-labelledby="resume-title">
      <h3 id="resume-title">Resume</h3>
      <p>
        {available
          ? "Your current security-scanned resume will be attached to this role."
          : "Sign in and add a security-scanned resume in your candidate profile before applying."}
      </p>
      {!available && <a href="/candidate/profile/">Open candidate profile</a>}
    </section>
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

function ApplicationForm({
  openingId,
  resumeId,
  consentId,
  request,
}: {
  openingId: string;
  resumeId?: string;
  consentId?: string;
  request: PageProps["request"];
}) {
  const [name, setName] = useState("");
  const [emailAddress, setEmailAddress] = useState("");
  const [motivation, setMotivation] = useState("");
  const [emailUpdates, setEmailUpdates] = useState(false);
  const [whatsappUpdates, setWhatsappUpdates] = useState(false);
  const [consented, setConsented] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const form = useRef<HTMLFormElement>(null);
  const ready = Boolean(resumeId && consentId);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!form.current?.reportValidity()) return;
    if (!ready) {
      setMessage(
        "Sign in and confirm role-specific consent before applying. Your details remain on this page.",
      );
      return;
    }
    setBusy(true);
    setMessage("Submitting application…");
    try {
      const response = await request("/api/v1/candidate/applications", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          opening_id: openingId,
          resume_id: resumeId,
          answers: { motivation },
          consent_record_id: consentId,
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
      setName("");
      setEmailAddress("");
      setMotivation("");
      setConsented(false);
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
        <Field label="Full name">
          {(props) => (
            <TextInput
              {...props}
              autoComplete="name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          )}
        </Field>
        <Field label="Verified email">
          {(props) => (
            <TextInput
              {...props}
              type="email"
              autoComplete="email"
              required
              value={emailAddress}
              onChange={(event) => setEmailAddress(event.target.value)}
            />
          )}
        </Field>
        <Field label="Why are you interested?">
          {(props) => (
            <Textarea
              {...props}
              value={motivation}
              onChange={(event) => setMotivation(event.target.value)}
            />
          )}
        </Field>
        <ResumeConsent available={Boolean(resumeId)} />
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

  return (
    <div className="ui-shell fm10-shell">
      <SkipLink />
      <PublicHeader />
      <main id="main" tabIndex={-1}>
        <Container width="public">
          {failed && (
            <EmptyState
              title="This role is unavailable"
              action={<a href="/jobs/">Return to open roles</a>}
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
                <section
                  className="fm10-description"
                  aria-labelledby="role-description"
                >
                  <h2 id="role-description">About this role</h2>
                  <p>{opening.description}</p>
                </section>
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
              <ApplicationForm
                openingId={opening.id}
                resumeId={bootstrap.resumeId}
                consentId={bootstrap.consentId}
                request={request}
              />
            </div>
          )}
        </Container>
      </main>
    </div>
  );
}
