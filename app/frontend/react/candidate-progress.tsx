import { useCallback, useEffect, useState } from "react";
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
  Loading,
  StatusMessage,
  WorkspaceNavigation,
} from "./components";
import type { PageProps } from "./mount";
import { visualAssets } from "./visual-assets";

type Status =
  | "APPLIED"
  | "PROFILE_VIEWED"
  | "SHORTLISTED"
  | "RECRUITER_INTERESTED"
  | "INTERVIEW_REQUESTED"
  | "OFFER_MADE"
  | "NOT_SELECTED"
  | "WITHDRAWN";
type Application = {
  id: string;
  opening_title: string;
  candidate_status: Status;
  status_updated_at: string;
  submitted_at: string;
  notification_preferences: { email: boolean; whatsapp: boolean };
  notification_states: { channel: string; state: string }[];
  status_history: { candidate_status: Status; updated_at: string }[];
};
const label = (value: string) =>
  value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (x) => x.toUpperCase());
const date = (value: string) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));

export function StatusTimeline({ application }: { application: Application }) {
  const items = application.status_history.length
    ? application.status_history
    : [
        {
          candidate_status: application.candidate_status,
          updated_at: application.status_updated_at,
        },
      ];
  return (
    <ol className="fm11-timeline" aria-label="Published application progress">
      {items.map((item, index) => (
        <li key={`${item.candidate_status}-${item.updated_at}-${index}`}>
          <span aria-hidden="true" />
          <div>
            <strong>{label(item.candidate_status)}</strong>
            <time dateTime={item.updated_at}>{date(item.updated_at)}</time>
          </div>
        </li>
      ))}
    </ol>
  );
}

function ChannelForm({
  application,
  request,
  onChanged,
}: {
  application: Application;
  request: PageProps["request"];
  onChanged: () => void;
}) {
  const [email, setEmail] = useState(
    application.notification_preferences.email,
  );
  const [whatsapp, setWhatsapp] = useState(
    application.notification_preferences.whatsapp,
  );
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    setMessage("Saving update channels…");
    try {
      const detail = await request(
        `/api/v1/candidate/applications/${application.id}`,
      );
      if (!detail.ok) throw new Error();
      const response = await request(
        `/api/v1/candidate/applications/${application.id}/notification-preferences`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "If-Match": detail.headers.get("ETag") ?? "",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({ email, whatsapp }),
        },
      );
      if (response.status === 409) {
        setMessage(
          "This application changed elsewhere. Nothing was overwritten; review the latest version and try again.",
        );
        return;
      }
      if (!response.ok) throw new Error();
      setMessage("Update channels saved.");
      onChanged();
    } catch {
      setMessage(
        "Channels could not be saved. Your application was not changed.",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section
      className="fm11-channels"
      aria-label={`Update channels for ${application.opening_title}`}
    >
      <h3>Update channels</h3>
      <Checkbox
        label="Email"
        checked={email}
        onChange={(e) => setEmail(e.target.checked)}
      />
      <Checkbox
        label="WhatsApp"
        checked={whatsapp}
        onChange={(e) => setWhatsapp(e.target.checked)}
      />
      <Button variant="secondary" busy={busy} onClick={() => void save()}>
        Save channels
      </Button>
      <StatusMessage>{message}</StatusMessage>
    </section>
  );
}

function ApplicationCard({
  application,
  request,
  reload,
}: {
  application: Application;
  request: PageProps["request"];
  reload: () => void;
}) {
  const [withdraw, setWithdraw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const confirm = async () => {
    setBusy(true);
    setMessage("Withdrawing application…");
    try {
      const detail = await request(
        `/api/v1/candidate/applications/${application.id}`,
      );
      if (!detail.ok) throw new Error();
      const response = await request(
        `/api/v1/candidate/applications/${application.id}/withdraw`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "If-Match": detail.headers.get("ETag") ?? "",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({
            candidate_status: "WITHDRAWN",
            confirm: true,
          }),
        },
      );
      if (response.status === 409) {
        setMessage(
          "This application changed elsewhere. Nothing was overwritten.",
        );
        setWithdraw(false);
        return;
      }
      if (!response.ok) throw new Error();
      setMessage("Application withdrawn.");
      setWithdraw(false);
      reload();
    } catch {
      setMessage("Withdrawal failed. The application remains active.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card data-application-id={application.id}>
      <div className="fm11-card-head">
        <div>
          <p className="fm11-kicker">Application</p>
          <h2>{application.opening_title}</h2>
        </div>
        <Chip
          tone={
            application.candidate_status === "WITHDRAWN" ||
            application.candidate_status === "NOT_SELECTED"
              ? "clay"
              : "sage"
          }
        >
          {label(application.candidate_status)}
        </Chip>
      </div>
      <StatusTimeline application={application} />
      <ChannelForm
        application={application}
        request={request}
        onChanged={reload}
      />
      {application.notification_states.length > 0 && (
        <ul aria-label="Notification delivery">
          {application.notification_states.map((item, i) => (
            <li key={`${item.channel}-${i}`}>
              {label(item.channel)}: {label(item.state)}
            </li>
          ))}
        </ul>
      )}
      {application.candidate_status !== "WITHDRAWN" && (
        <Button variant="danger" onClick={() => setWithdraw(true)}>
          Withdraw this application
        </Button>
      )}
      <StatusMessage>{message}</StatusMessage>
      <Dialog
        open={withdraw}
        onClose={() => setWithdraw(false)}
        title="Withdraw this application?"
      >
        <p>
          This stops this application only. It does not delete your candidate
          profile or other applications.
        </p>
        <div className="ui-row">
          <Button variant="danger" busy={busy} onClick={() => void confirm()}>
            Yes, withdraw application
          </Button>
          <Button variant="secondary" onClick={() => setWithdraw(false)}>
            Keep application
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}

export function ProgressPage({ request }: PageProps) {
  const [items, setItems] = useState<Application[]>();
  const [failed, setFailed] = useState(false);
  const [signOutFailed, setSignOutFailed] = useState(false);
  const load = useCallback(async () => {
    setFailed(false);
    try {
      const response = await request("/api/v1/candidate/applications");
      if (!response.ok) throw new Error();
      setItems((await response.json()) as Application[]);
    } catch {
      setFailed(true);
    }
  }, [request]);
  useEffect(() => void load(), [load]);
  return (
    <AppShell
      title="Your applications"
      navigation={
        <>
          <WorkspaceNavigation
            label="Candidate navigation"
            items={[
              { label: "Resume & profile", href: "/candidate/profile/" },
              {
                label: "My applications",
                href: "/candidate/applications/",
                current: true,
              },
              { label: "Privacy rights", href: "/candidate/rights/" },
            ]}
          />
          <Button
            variant="secondary"
            onClick={async () => {
              setSignOutFailed(false);
              try {
                const response = await request("/api/v1/session/sign-out", {
                  method: "DELETE",
                });
                if (!response.ok) throw new Error();
                location.replace("/");
              } catch {
                setSignOutFailed(true);
              }
            }}
          >
            Sign out
          </Button>
        </>
      }
    >
      <p>
        Follow published progress and choose how each role may send updates.
      </p>
      <aside
        className="fm11-status-key"
        aria-label="Possible application statuses"
      >
        <strong>Progress stages</strong>
        <p>
          Applied · Profile viewed · Shortlisted · Recruiter interested ·
          Interview requested · Offer made · Not selected · Withdrawn
        </p>
      </aside>
      {signOutFailed && (
        <Alert>Sign-out failed. Your session remains active; try again.</Alert>
      )}
      {failed && <ErrorState onRetry={() => void load()} />}
      {!failed && !items && <Loading label="Loading applications…" />}
      {!failed && items?.length === 0 && (
        <EmptyState
          title="No applications yet"
          illustration={{
            src: visualAssets.applicationJourneyEmpty,
            width: 1024,
            height: 1024,
          }}
          action={
            <a className="ui-button" href="/candidate/profile/">
              Return to your profile
            </a>
          }
        >
          There are no application records linked to your profile.
        </EmptyState>
      )}
      <div className="fm11-application-list">
        {items?.map((item) => (
          <ApplicationCard
            key={item.id}
            application={item}
            request={request}
            reload={() => void load()}
          />
        ))}
      </div>
    </AppShell>
  );
}

export const CandidateProgress = ProgressPage;
