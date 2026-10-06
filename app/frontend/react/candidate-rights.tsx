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
  Field,
  Loading,
  StatusMessage,
  TextInput,
  Textarea,
  WorkspaceNavigation,
} from "./components";
import type { PageProps } from "./mount";

type RequestType =
  | "ACCESS"
  | "CORRECTION"
  | "WITHDRAW_CONSENT"
  | "HIDE_PROFILE"
  | "EXPORT"
  | "DELETE";
type RightsItem = {
  id: string;
  request_type: RequestType;
  state:
    | "PENDING"
    | "IN_PROGRESS"
    | "HELD"
    | "COMPLETED"
    | "FAILED"
    | "CANCELLED";
  submitted_at: string;
  expected_completion_at: string;
  completed_at: string | null;
  safe_detail: string | null;
  exception_scope: string[] | null;
  support_escalation_available: boolean;
};
const label = (value: string) =>
  value
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (x) => x.toUpperCase());

export function RightsRequest({
  item,
  request,
  reload,
}: {
  item: RightsItem;
  request: PageProps["request"];
  reload: () => void;
}) {
  const [escalate, setEscalate] = useState(false);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const download = async () => {
    const response = await request(
      `/api/v1/candidate/rights-requests/${item.id}/download`,
      { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } },
    );
    if (!response.ok) {
      setMessage(
        "The export is unavailable or its 24-hour download window has expired.",
      );
      return;
    }
    const payload = await response.blob();
    const url = URL.createObjectURL(payload);
    const link = document.createElement("a");
    link.href = url;
    link.download = `enter-data-export-${item.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setMessage("Authenticated export downloaded. The link is not retained.");
  };
  const send = async () => {
    const response = await request(
      `/api/v1/candidate/rights-requests/${item.id}/escalations`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ reason }),
      },
    );
    setMessage(
      response.ok
        ? "Privacy support has received your request."
        : "Support escalation could not be sent.",
    );
    if (response.ok) {
      setEscalate(false);
      reload();
    }
  };
  return (
    <Card>
      <div className="fm11-card-head">
        <div>
          <p className="fm11-kicker">{label(item.request_type)}</p>
          <h3>Submitted {new Date(item.submitted_at).toLocaleDateString()}</h3>
        </div>
        <Chip
          tone={
            item.state === "COMPLETED"
              ? "sage"
              : item.state === "FAILED"
                ? "clay"
                : "gold"
          }
        >
          {label(item.state)}
        </Chip>
      </div>
      <p>{item.safe_detail ?? "No additional detail is available."}</p>
      <p>
        <strong>Expected by:</strong>{" "}
        {new Date(item.expected_completion_at).toLocaleString()}
      </p>
      {item.exception_scope?.length ? (
        <Alert tone="gold">
          Some records are retained temporarily:{" "}
          {item.exception_scope.join(", ")}.
        </Alert>
      ) : null}
      <div className="ui-row">
        {item.request_type === "EXPORT" && item.state === "COMPLETED" && (
          <Button onClick={() => void download()}>Download export</Button>
        )}
        {item.support_escalation_available && (
          <Button variant="secondary" onClick={() => setEscalate(true)}>
            Ask privacy support
          </Button>
        )}
      </div>
      <StatusMessage>{message}</StatusMessage>
      <Dialog
        open={escalate}
        onClose={() => setEscalate(false)}
        title="Ask privacy support for help"
      >
        <Field
          label="Reason"
          help="Do not include unnecessary sensitive information."
        >
          {(props) => (
            <Textarea
              {...props}
              maxLength={2000}
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          )}
        </Field>
        <Button disabled={!reason.trim()} onClick={() => void send()}>
          Send to support
        </Button>
      </Dialog>
    </Card>
  );
}

export function RightsCenter({ request }: PageProps) {
  const [items, setItems] = useState<RightsItem[]>();
  const [failed, setFailed] = useState(false);
  const [message, setMessage] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [proof, setProof] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const load = useCallback(async () => {
    setFailed(false);
    try {
      const response = await request("/api/v1/candidate/rights-requests");
      if (!response.ok) throw new Error();
      setItems((await response.json()) as RightsItem[]);
    } catch {
      setFailed(true);
    }
  }, [request]);
  useEffect(() => void load(), [load]);
  const create = async (
    requestType: RequestType,
    extra: Record<string, unknown> = {},
  ) => {
    setMessage(`Submitting ${label(requestType)} request…`);
    const response = await request("/api/v1/candidate/rights-requests", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ request_type: requestType, ...extra }),
    });
    if (!response.ok) {
      setMessage(
        requestType === "DELETE"
          ? "Deletion was not requested. Complete recent identity verification and check the confirmation before retrying."
          : "The privacy request could not be submitted.",
      );
      return;
    }
    setMessage(`${label(requestType)} request accepted.`);
    setDeleting(false);
    setProof("");
    setConfirmed(false);
    void load();
  };
  return (
    <AppShell
      title="Your data rights"
      navigation={
        <WorkspaceNavigation
          label="Candidate navigation"
          items={[
            { label: "Resume & profile", href: "/candidate/profile/" },
            {
              label: "My applications",
              href: "/candidate/applications/",
            },
            {
              label: "Privacy rights",
              href: "/candidate/rights/",
              current: true,
            },
          ]}
        />
      }
    >
      <p>
        Access and profile-control requests are immediate. Exports are prepared
        within 24 hours. Deletion requires recent identity verification and may
        take up to 30 days.
      </p>
      <section aria-labelledby="rights-actions">
        <h2 id="rights-actions">Choose an action</h2>
        <div className="fm11-rights-grid">
          <Button onClick={() => void create("ACCESS")}>Access my data</Button>
          <Button onClick={() => void create("EXPORT")}>
            Request an export
          </Button>
          <Button
            variant="secondary"
            onClick={() => void create("WITHDRAW_CONSENT")}
          >
            Withdraw consent
          </Button>
          <Button
            variant="secondary"
            onClick={() => void create("HIDE_PROFILE")}
          >
            Hide my profile
          </Button>
          <a className="ui-button" href="/candidate/profile/">
            Correct profile data
          </a>
          <Button variant="danger" onClick={() => setDeleting(true)}>
            Request deletion
          </Button>
        </div>
      </section>
      <StatusMessage>{message}</StatusMessage>
      <section aria-labelledby="request-history">
        <h2 id="request-history">Request history</h2>
        {failed && <ErrorState onRetry={() => void load()} />}
        {!failed && !items && <Loading label="Loading privacy requests…" />}
        {items?.length === 0 && (
          <EmptyState title="No privacy requests">
            Your requests and their deadlines will appear here.
          </EmptyState>
        )}
        <div className="fm11-rights-list">
          {items?.map((item) => (
            <RightsRequest
              key={item.id}
              item={item}
              request={request}
              reload={() => void load()}
            />
          ))}
        </div>
      </section>
      <Dialog
        open={deleting}
        onClose={() => setDeleting(false)}
        title="Confirm profile deletion"
      >
        <Alert tone="gold">
          Your profile is hidden immediately. Deletion completes within 30 days
          except for specifically identified active-process or legal-hold
          records.
        </Alert>
        <Field
          label="Recent verification reference"
          help="Use the proof supplied by the recent identity-verification step."
        >
          {(props) => (
            <TextInput
              {...props}
              required
              value={proof}
              onChange={(e) => setProof(e.target.value)}
            />
          )}
        </Field>
        <Checkbox
          label="I understand these consequences and want to request deletion."
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        <div className="ui-row">
          <Button
            variant="danger"
            disabled={!confirmed || !proof.trim()}
            onClick={() =>
              void create("DELETE", {
                confirm_consequences: true,
                step_up_proof: proof.trim(),
              })
            }
          >
            Confirm deletion request
          </Button>
          <Button variant="secondary" onClick={() => setDeleting(false)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </AppShell>
  );
}

export const CandidateRights = RightsCenter;
