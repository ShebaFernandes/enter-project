import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  Alert,
  AppShell,
  Button,
  Card,
  Chip,
  Dialog,
  EmptyState,
  Field,
  Loading,
  Select,
  StatusMessage,
  TextInput,
  WorkspaceNavigation,
} from "./components";
import type { PageBootstrap, PageProps } from "./mount";

type Request = PageProps["request"];
type AuditEvent = {
  id: string;
  occurred_at: string;
  effective_role: string;
  action: string;
  target_type: string;
  outcome: "ALLOWED" | "DENIED" | "FAILED";
  reason_code: string | null;
};
type ReviewItem = {
  id: string;
  assignment_type: string;
  evidence: Record<string, unknown>;
  decision: "PENDING" | "RETAIN" | "REVOKE" | "EXCEPTION";
};
type AccessReview = {
  id: string;
  review_type: string;
  state: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "OVERDUE";
  due_at: string;
  remediation_state: string;
  etag: string;
  version: number;
  items: ReviewItem[];
};
type EmergencyAccess = NonNullable<PageBootstrap["emergencyAccess"]>[number];
type Decision = {
  decision: "" | "RETAIN" | "REVOKE" | "EXCEPTION";
  finding: string;
  exception_owner_id: string;
  exception_expires_at: string;
};
type Section = "overview" | "audit" | "reviews" | "emergency";

const writeHeaders = () => ({
  "Content-Type": "application/json",
  "Idempotency-Key": crypto.randomUUID(),
});
const formatDate = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "Unavailable";
const tone = (value: string) =>
  value === "ALLOWED" || value === "COMPLETED" || value === "ACTIVE"
    ? "sage"
    : value === "DENIED" || value === "FAILED" || value === "OVERDUE"
      ? "clay"
      : "gold";

export function RedactedAudit({
  base,
  request,
  setMessage,
}: {
  base: string;
  request: Request;
  setMessage: (value: string) => void;
}) {
  const [events, setEvents] = useState<AuditEvent[]>();
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    setFailed(false);
    setMessage("Loading redacted audit metadata…");
    const response = await request(base + "/audit-events");
    if (!response.ok) {
      setFailed(true);
      setEvents(undefined);
      setMessage(
        "Audit metadata is unavailable. The failed read remains server-audited.",
      );
      return;
    }
    setEvents((await response.json()) as AuditEvent[]);
    setMessage("Redacted audit metadata loaded. This read was audited.");
  }, [base, request, setMessage]);
  useEffect(() => void load(), [load]);
  if (!events && !failed) return <Loading label="Loading audit metadata…" />;
  if (failed)
    return (
      <Alert>
        Current audit metadata could not be loaded. No cached copy is shown.
        <Button variant="secondary" onClick={() => void load()}>
          Try audit read again
        </Button>
      </Alert>
    );
  return (
    <Card title="Redacted audit metadata">
      <p>
        Every read is audited. Candidate content and sensitive values are not
        included in this administrative projection.
      </p>
      {events?.length ? (
        <ol className="fm13-audit-list">
          {events.map((event) => (
            <li key={event.id}>
              <div className="fm13-card-head">
                <strong>{event.action}</strong>
                <Chip tone={tone(event.outcome)}>{event.outcome}</Chip>
              </div>
              <p>
                {event.target_type} · {event.effective_role} ·{" "}
                {formatDate(event.occurred_at)}
              </p>
              {event.reason_code && <p>Reason: {event.reason_code}</p>}
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState title="No audit metadata">
          No authorized audit events are currently available.
        </EmptyState>
      )}
    </Card>
  );
}

function Evidence({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value).filter(
    ([, item]) =>
      typeof item === "string" ||
      typeof item === "number" ||
      typeof item === "boolean" ||
      (Array.isArray(item) && item.every((part) => typeof part === "string")),
  );
  return (
    <dl className="fm13-evidence">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>{Array.isArray(item) ? item.join(", ") : String(item)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ReviewDecision({
  review,
  base,
  request,
  reload,
  setMessage,
}: {
  review: AccessReview;
  base: string;
  request: Request;
  reload: () => void;
  setMessage: (value: string) => void;
}) {
  const pending = review.items.filter((item) => item.decision === "PENDING");
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const update = (id: string, patch: Partial<Decision>) =>
    setDecisions((current) => {
      const existing = current[id] ?? {
        decision: "",
        finding: "",
        exception_owner_id: "",
        exception_expires_at: "",
      };
      return {
        ...current,
        [id]: {
          ...existing,
          ...patch,
        },
      };
    });
  const complete = pending.every((item) => {
    const value = decisions[item.id];
    return Boolean(
      value?.decision &&
        (value.decision !== "EXCEPTION" ||
          (value.exception_owner_id && value.exception_expires_at)),
    );
  });
  const submit = async () => {
    setBusy(true);
    const response = await request(
      base + "/access-reviews/" + review.id + "/complete",
      {
        method: "POST",
        headers: { ...writeHeaders(), "If-Match": review.etag },
        body: JSON.stringify({
          decisions: pending.map((item) => {
            const value = decisions[item.id];
            return {
              item_id: item.id,
              decision: value.decision,
              finding: value.finding,
              ...(value.decision === "EXCEPTION"
                ? {
                    exception_owner_id: value.exception_owner_id,
                    exception_expires_at: value.exception_expires_at,
                  }
                : {}),
            };
          }),
        }),
      },
    );
    setBusy(false);
    setConfirming(false);
    if (response.status === 409) {
      setMessage(
        "Review changed; no decisions were applied. Reloaded current evidence.",
      );
      reload();
      return;
    }
    if (!response.ok) {
      setMessage("Review was not completed. No decision is assumed.");
      return;
    }
    setMessage("Review completed and governance evidence recorded.");
    reload();
  };
  return (
    <section
      className="fm13-review"
      aria-label={review.review_type + " access review"}
    >
      <div className="fm13-card-head">
        <div>
          <h3>{review.review_type.replaceAll("_", " ")}</h3>
          <p>Due {formatDate(review.due_at)}</p>
        </div>
        <Chip tone={tone(review.state)}>{review.state}</Chip>
      </div>
      <p>Remediation: {review.remediation_state.replaceAll("_", " ")}</p>
      {pending.map((item, index) => {
        const value = decisions[item.id] ?? {
          decision: "",
          finding: "",
          exception_owner_id: "",
          exception_expires_at: "",
        };
        return (
          <fieldset className="fm13-review-item" key={item.id}>
            <legend>
              Item {index + 1}: {item.assignment_type.replaceAll("_", " ")}
            </legend>
            <Evidence value={item.evidence} />
            <Field label={"Decision for item " + (index + 1)}>
              {(props) => (
                <Select
                  {...props}
                  value={value.decision}
                  onChange={(event) =>
                    update(item.id, {
                      decision: event.target.value as Decision["decision"],
                    })
                  }
                >
                  <option value="">Select a decision</option>
                  <option value="RETAIN">Retain</option>
                  <option value="REVOKE">Revoke</option>
                  <option value="EXCEPTION">Bounded exception</option>
                </Select>
              )}
            </Field>
            <Field label={"Finding for item " + (index + 1)}>
              {(props) => (
                <TextInput
                  {...props}
                  value={value.finding}
                  maxLength={500}
                  onChange={(event) =>
                    update(item.id, { finding: event.target.value })
                  }
                />
              )}
            </Field>
            {value.decision === "EXCEPTION" && (
              <div className="fm13-exception">
                <Field
                  label={"Exception owner ID for item " + (index + 1)}
                  help="Must be an active tenant member responsible for the exception."
                >
                  {(props) => (
                    <TextInput
                      {...props}
                      required
                      value={value.exception_owner_id}
                      onChange={(event) =>
                        update(item.id, {
                          exception_owner_id: event.target.value,
                        })
                      }
                    />
                  )}
                </Field>
                <Field label={"Exception expiry for item " + (index + 1)}>
                  {(props) => (
                    <TextInput
                      {...props}
                      type="datetime-local"
                      required
                      value={value.exception_expires_at}
                      onChange={(event) =>
                        update(item.id, {
                          exception_expires_at: event.target.value,
                        })
                      }
                    />
                  )}
                </Field>
              </div>
            )}
          </fieldset>
        );
      })}
      {pending.length > 0 && (
        <Button disabled={!complete} onClick={() => setConfirming(true)}>
          Complete review
        </Button>
      )}
      {pending.length === 0 && (
        <p>No pending decisions remain in this review.</p>
      )}
      <Dialog
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Confirm access review decisions"
      >
        <p>
          Revocations take effect immediately. Exceptions require the recorded
          owner and expiry. Candidate content is not disclosed by this action.
        </p>
        <div className="ui-row">
          <Button busy={busy} onClick={() => void submit()}>
            Confirm decisions
          </Button>
          <Button variant="secondary" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </section>
  );
}

export function AccessReviewList({
  base,
  request,
  setMessage,
}: {
  base: string;
  request: Request;
  setMessage: (value: string) => void;
}) {
  const [reviews, setReviews] = useState<AccessReview[]>();
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setFailed(false);
    const response = await request(base + "/access-reviews");
    if (!response.ok) {
      setFailed(true);
      setReviews(undefined);
      setMessage("Access reviews are unavailable. No cached copy is shown.");
      return;
    }
    setReviews((await response.json()) as AccessReview[]);
  }, [base, request, setMessage]);
  useEffect(() => void load(), [load]);
  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    const response = await request(base + "/access-reviews", {
      method: "POST",
      headers: writeHeaders(),
      body: JSON.stringify({
        review_type: data.get("review_type"),
        due_at: data.get("due_at"),
      }),
    });
    setBusy(false);
    if (!response.ok) {
      setMessage("Access review was not started.");
      return;
    }
    form.reset();
    setMessage("Access review started.");
    void load();
  };
  return (
    <Card title="Access reviews">
      <p>
        Review memberships, privileged roles, purpose grants, emergency grants
        and audit access. Decisions are server-authorized and recorded.
      </p>
      <form className="fm13-create" onSubmit={(event) => void create(event)}>
        <Field label="Review type">
          {(props) => (
            <Select {...props} name="review_type">
              <option>MEMBERSHIP</option>
              <option>PRIVILEGED_ROLE</option>
              <option>PURPOSE_GRANT</option>
              <option>EMERGENCY_GRANT</option>
              <option>AUDIT_ACCESS</option>
            </Select>
          )}
        </Field>
        <Field label="Due date">
          {(props) => (
            <TextInput
              {...props}
              name="due_at"
              type="datetime-local"
              required
            />
          )}
        </Field>
        <Button type="submit" busy={busy}>
          Start access review
        </Button>
      </form>
      {!reviews && !failed && <Loading label="Loading access reviews…" />}
      {failed && (
        <Alert>
          Current review data could not be loaded. No cached copy is shown.
          <Button variant="secondary" onClick={() => void load()}>
            Try review load again
          </Button>
        </Alert>
      )}
      {reviews?.length === 0 && (
        <EmptyState title="No access reviews">
          Start the next required governance review above.
        </EmptyState>
      )}
      <div className="fm13-review-list">
        {reviews?.map((review) => (
          <ReviewDecision
            key={review.id}
            review={review}
            base={base}
            request={request}
            reload={() => void load()}
            setMessage={setMessage}
          />
        ))}
      </div>
    </Card>
  );
}

export function EmergencyAccessPanel({
  initial,
  base,
  request,
  setMessage,
}: {
  initial: EmergencyAccess[];
  base: string;
  request: Request;
  setMessage: (value: string) => void;
}) {
  const [items, setItems] = useState(initial);
  const [selected, setSelected] = useState<EmergencyAccess>();
  const [busy, setBusy] = useState(false);
  const revoke = async () => {
    if (!selected) return;
    setBusy(true);
    const response = await request(
      base + "/emergency-access-grants/" + selected.id + "/revoke",
      { method: "POST", headers: writeHeaders() },
    );
    setBusy(false);
    if (!response.ok) {
      setMessage("Emergency access was not revoked.");
      setSelected(undefined);
      return;
    }
    setItems((current) => current.filter((item) => item.id !== selected.id));
    setSelected(undefined);
    setMessage("Emergency access revoked.");
  };
  return (
    <Card title="Emergency access">
      <Alert tone="gold">
        Tenant Admins can inspect only minimized scope and expiry metadata. This
        does not grant access to candidate content.
      </Alert>
      {items.length ? (
        <ul className="fm13-emergency-list">
          {items.map((item) => (
            <li key={item.id}>
              <div className="fm13-card-head">
                <strong>{item.reason_code}</strong>
                <Chip tone={tone(item.status)}>{item.status}</Chip>
              </div>
              <p>
                {item.operation_scope.join(", ")} · fields{" "}
                {item.field_scope.join(", ")} · {item.object_count} scoped
                object(s) · expires {formatDate(item.expires_at)}
              </p>
              <Button variant="danger" onClick={() => setSelected(item)}>
                Revoke emergency access
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="No active emergency access">
          There are no active grants for this tenant.
        </EmptyState>
      )}
      <Dialog
        open={Boolean(selected)}
        onClose={() => setSelected(undefined)}
        title="Confirm emergency-access revocation"
      >
        <p>
          Revoke this exact scoped grant immediately? This action does not show
          candidate content.
        </p>
        <div className="ui-row">
          <Button variant="danger" busy={busy} onClick={() => void revoke()}>
            Confirm revocation
          </Button>
          <Button variant="secondary" onClick={() => setSelected(undefined)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </Card>
  );
}

export function GovernancePage({ bootstrap, request }: PageProps) {
  const tenantId = bootstrap.tenantId ?? "";
  const base = "/api/v1/tenants/" + tenantId;
  const [section, setSection] = useState<Section>("overview");
  const [message, setMessage] = useState("");
  const tabs = useMemo(
    () =>
      [
        ["overview", "Overview"],
        ["audit", "Audit metadata"],
        ["reviews", "Access reviews"],
        ["emergency", "Emergency access"],
      ] as const,
    [],
  );
  const choose = (value: Section) => {
    setMessage("");
    setSection(value);
  };
  const keydown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? tabs.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
            tabs.length;
    const target =
      event.currentTarget.parentElement?.querySelectorAll("button")[next];
    target?.focus();
    choose(tabs[next][0]);
  };
  return (
    <AppShell
      title="Tenant governance"
      navigation={
        <WorkspaceNavigation
          label="Tenant Admin navigation"
          items={[
            {
              label: "Governance",
              href: "/tenants/" + tenantId + "/admin/governance/",
              current: true,
            },
          ]}
        />
      }
    >
      <p>
        Administrative metadata only. This workspace does not grant access to
        candidate content.
      </p>
      <div
        className="fm13-tabs"
        role="tablist"
        aria-label="Governance sections"
      >
        {tabs.map(([value, label], index) => (
          <button
            type="button"
            role="tab"
            key={value}
            aria-selected={section === value}
            aria-controls={"fm13-" + value}
            id={"fm13-" + value + "-tab"}
            tabIndex={section === value ? 0 : -1}
            onClick={() => choose(value)}
            onKeyDown={(event) => keydown(event, index)}
          >
            {label}
          </button>
        ))}
      </div>
      <StatusMessage>{message}</StatusMessage>
      <section
        id={"fm13-" + section}
        role="tabpanel"
        aria-labelledby={"fm13-" + section + "-tab"}
        className="fm13-panel"
      >
        {section === "overview" && (
          <div className="fm13-overview">
            <Card title="Governance boundaries">
              <p>
                Review administrative assignments and redacted evidence without
                receiving automatic access to profiles, resumes or contact data.
              </p>
            </Card>
            <Card title="Recorded controls">
              <ul>
                <li>Audit-history reads are themselves audited.</li>
                <li>
                  Stale access-review decisions never overwrite newer work.
                </li>
                <li>Revocations are explicit and bounded exceptions expire.</li>
              </ul>
            </Card>
          </div>
        )}
        {section === "audit" && (
          <RedactedAudit
            base={base}
            request={request}
            setMessage={setMessage}
          />
        )}
        {section === "reviews" && (
          <AccessReviewList
            base={base}
            request={request}
            setMessage={setMessage}
          />
        )}
        {section === "emergency" && (
          <EmergencyAccessPanel
            initial={bootstrap.emergencyAccess ?? []}
            base={base}
            request={request}
            setMessage={setMessage}
          />
        )}
      </section>
    </AppShell>
  );
}
