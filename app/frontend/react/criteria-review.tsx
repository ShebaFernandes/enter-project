import { useEffect, useRef, useState, type ComponentProps } from "react";
import type { PageProps } from "./mount";
import {
  Alert,
  AppShell,
  Button,
  Chip,
  ConflictPanel,
  EmptyState,
  Field,
  Loading,
  Select,
  StatusMessage,
  TextInput,
} from "./components";
import { ApiError, responseJson } from "../shared/api-client";
import { handoffToken, workflowTransport } from "../shared/workflow-handoff";

type Group = {
  id: string;
  label?: string | null;
  purpose: "REQUIREMENT" | "PREFERENCE" | "EXCLUSION";
  operator: "ANY" | "ALL";
};
type Criterion = {
  id: string;
  group_id: string;
  field: string;
  operator: string;
  value: string | number | boolean | string[];
};
export type Criteria = {
  context: Record<string, string>;
  groups: Group[];
  criteria: Criterion[];
  limit: number;
};
type Review = {
  etag: string;
  criteria: Criteria;
  estimated_count: number;
  group_impacts?: {
    group_id: string;
    operator: string;
    estimated_count: number;
    alternate_operator: string;
    alternate_estimated_count: number;
  }[];
};
const fields = {
  skill: "Skill",
  experience_years: "Experience",
  location: "Location",
  work_arrangement: "Work arrangement",
  availability_date: "Availability",
  role_category: "Role category",
};
const operators = [
  "CONTAINS",
  "EQ",
  "NE",
  "LT",
  "LTE",
  "GT",
  "GTE",
  "IN",
  "NOT_IN",
  "EXISTS",
];
const serial = (value: unknown) => JSON.stringify(value);
const valueText = (value: Criterion["value"]) =>
  typeof value === "string" ? value : serial(value);
function editedValue(
  value: string,
  previous: Criterion["value"],
  operator: string,
): Criterion["value"] {
  // Preserve strings as entered; typed values retain their type only when explicitly valid.
  if (
    typeof previous === "string" &&
    !["IN", "NOT_IN", "EXISTS"].includes(operator)
  )
    return value;
  try {
    const parsed: unknown = JSON.parse(value);
    if (
      typeof parsed === "number" ||
      typeof parsed === "boolean" ||
      (Array.isArray(parsed) && parsed.every((v) => typeof v === "string"))
    )
      return parsed as Criterion["value"];
  } catch {
    /* Server validates incomplete edits. */
  }
  return value;
}
function focusValue(id: string) {
  requestAnimationFrame(() =>
    document
      .querySelector<HTMLInputElement>(`[data-value-id="${id}"]`)
      ?.focus(),
  );
}

function CriterionEditor({
  criterion,
  groups,
  change,
  remove,
}: {
  criterion: Criterion;
  groups: Group[];
  change: (value: Criterion) => void;
  remove: () => void;
}) {
  return (
    <fieldset className="review-criterion">
      <legend>Criterion</legend>
      <div className="review-grid">
        <Field label="Group membership">
          {(p) => (
            <Select
              {...p}
              value={criterion.group_id}
              onChange={(e) => {
                change({ ...criterion, group_id: e.target.value });
                focusValue(criterion.id);
              }}
            >
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label || g.purpose}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Field">
          {(p) => (
            <Select
              {...p}
              value={criterion.field}
              onChange={(e) => change({ ...criterion, field: e.target.value })}
            >
              {Object.entries(fields).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Operator">
          {(p) => (
            <Select
              {...p}
              value={criterion.operator}
              onChange={(e) =>
                change({ ...criterion, operator: e.target.value })
              }
            >
              {operators.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          label="Value"
          help={
            ["IN", "NOT_IN"].includes(criterion.operator)
              ? 'Enter a JSON list of text values, for example ["Python", "Django"].'
              : criterion.operator === "EXISTS"
                ? "Enter true or false."
                : undefined
          }
        >
          {(p) => (
            <TextInput
              {...p}
              data-value-id={criterion.id}
              required
              value={valueText(criterion.value)}
              onChange={(e) =>
                change({
                  ...criterion,
                  value: editedValue(
                    e.target.value,
                    criterion.value,
                    criterion.operator,
                  ),
                })
              }
            />
          )}
        </Field>
      </div>
      <details>
        <summary>Criterion reference</summary>
        <span className="review-reference">{criterion.id}</span>
      </details>
      <Button variant="secondary" onClick={remove}>
        Remove criterion
      </Button>
    </fieldset>
  );
}
function ImpactSummary({ review }: { review: Review }) {
  return (
    <div className="review-impact">
      <span>Estimated candidates</span>
      <strong>{review.estimated_count}</strong>
      <span>Estimate only · not a result set</span>
    </div>
  );
}
function GroupEditor({
  group,
  draft,
  review,
  change,
}: {
  group: Group;
  draft: Criteria;
  review: Review;
  change: (value: Criteria) => void;
}) {
  const impact = review.group_impacts?.find(
    (item) => item.group_id === group.id,
  );
  const update = (value: Group) =>
    change({
      ...draft,
      groups: draft.groups.map((g) => (g.id === group.id ? value : g)),
    });
  return (
    <fieldset className="review-group">
      <legend>
        <Chip
          tone={
            group.purpose === "PREFERENCE"
              ? "sage"
              : group.purpose === "EXCLUSION"
                ? "clay"
                : "gold"
          }
        >
          {group.label || "Criteria group"}
        </Chip>
      </legend>
      <div className="review-grid">
        <Field label="Group label">
          {(p) => (
            <TextInput
              {...p}
              maxLength={200}
              value={group.label ?? ""}
              onChange={(e) => update({ ...group, label: e.target.value })}
            />
          )}
        </Field>
        <Field label="Purpose">
          {(p) => (
            <Select
              {...p}
              value={group.purpose}
              onChange={(e) =>
                update({
                  ...group,
                  purpose: e.target.value as Group["purpose"],
                })
              }
            >
              {["REQUIREMENT", "PREFERENCE", "EXCLUSION"].map((purpose) => (
                <option key={purpose}>{purpose}</option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          label="Match within group"
          help="ANY matches one criterion. ALL requires every criterion."
        >
          {(p) => (
            <Select
              {...p}
              value={group.operator}
              onChange={(e) =>
                update({
                  ...group,
                  operator: e.target.value as Group["operator"],
                })
              }
            >
              <option>ALL</option>
              <option>ANY</option>
            </Select>
          )}
        </Field>
      </div>
      <p className="ui-help">
        {impact
          ? `Estimated impact: ${impact.operator} ${impact.estimated_count}; ${impact.alternate_operator} ${impact.alternate_estimated_count} candidates.`
          : "Estimated impact updates after valid criteria are entered."}
      </p>
      {draft.criteria
        .filter((c) => c.group_id === group.id)
        .map((criterion) => (
          <CriterionEditor
            key={criterion.id}
            criterion={criterion}
            groups={draft.groups}
            change={(value) =>
              change({
                ...draft,
                criteria: draft.criteria.map((c) =>
                  c.id === value.id ? value : c,
                ),
              })
            }
            remove={() => {
              change({
                ...draft,
                criteria: draft.criteria.filter((c) => c.id !== criterion.id),
              });
              requestAnimationFrame(() =>
                document.getElementById(`add-${group.id}`)?.focus(),
              );
            }}
          />
        ))}
      <div className="ui-row">
        <Button
          id={`add-${group.id}`}
          variant="secondary"
          onClick={() => {
            const id = crypto.randomUUID();
            change({
              ...draft,
              criteria: [
                ...draft.criteria,
                {
                  id,
                  group_id: group.id,
                  field: "skill",
                  operator: "CONTAINS",
                  value: "",
                },
              ],
            });
            focusValue(id);
          }}
        >
          Add criterion
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            change({
              ...draft,
              groups: draft.groups.filter((g) => g.id !== group.id),
              criteria: draft.criteria.filter((c) => c.group_id !== group.id),
            });
            requestAnimationFrame(() =>
              document.getElementById("add-group")?.focus(),
            );
          }}
        >
          Remove group
        </Button>
      </div>
    </fieldset>
  );
}

function ReviewFrame({
  embedded,
  ...props
}: ComponentProps<typeof AppShell> & { embedded: boolean }) {
  return embedded ? (
    <section aria-label="Adjust search criteria">{props.children}</section>
  ) : (
    <AppShell {...props} />
  );
}

export function CriteriaReview({
  bootstrap,
  request,
  embeddedToken,
}: PageProps & { embeddedToken?: string }) {
  const tenant = bootstrap.tenantId ?? "";
  const [token] = useState(() => embeddedToken ?? handoffToken());
  const endpoint = `/api/v1/tenants/${tenant}/search-handoffs/criteria-review`;
  const [review, setReview] = useState<Review | null>(null);
  const [draft, setDraft] = useState<Criteria | null>(null);
  const [conflict, setConflict] = useState<Review | null>(null);
  const [merging, setMerging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [completedSearch, setCompletedSearch] = useState<string | null>(null);
  const locked = useRef(false);
  const lastAttempt = useRef("");
  const retryKey = useRef(crypto.randomUUID());
  const headers = { "X-Workflow-Handoff": token ?? "" };
  async function restore() {
    return (await responseJson<Review>(await request(endpoint, { headers })))
      .data;
  }
  async function load() {
    setLoading(true);
    setError("");
    try {
      if (!token) throw new ApiError(404, null);
      const current = await restore();
      setReview(current);
      setDraft(current.criteria);
      setStatus("Criteria restored. Review before confirming.");
    } catch (failure) {
      await handleFailure(failure);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []); // A mount is bound to one server context and fragment.
  async function handleFailure(failure: unknown) {
    if (
      failure instanceof ApiError &&
      [401, 403, 404, 410].includes(failure.status)
    ) {
      setUnavailable(true);
      setReview(null);
      setDraft(null);
      setConflict(null);
      setError(
        "Review expired, was revoked or is unavailable for this session. Return to search.",
      );
    } else if (failure instanceof ApiError && failure.status === 409) {
      try {
        setConflict(await restore());
        setError("");
      } catch (next) {
        if (next instanceof ApiError && next.status === 409)
          setError(
            "The workflow changed. Return to search for a fresh review.",
          );
        else await handleFailure(next);
      }
    } else if (failure instanceof ApiError && failure.status === 429)
      setError(
        "Too many requests. Wait before retrying; your edits remain here.",
      );
    else if (failure instanceof ApiError && [400, 422].includes(failure.status))
      setError(
        "The server could not validate these criteria. Review fields, operators, values and group membership before retrying.",
      );
    else
      setError(
        "Estimated impact or restoration is unavailable. Your edits remain here; retry when the service is available.",
      );
  }
  async function persist(value: Criteria, current: Review) {
    const { data } = await responseJson<Review>(
      await request(endpoint, {
        method: "PATCH",
        headers: {
          ...headers,
          "Content-Type": "application/json",
          "If-Match": current.etag,
        },
        body: serial({ criteria: value }),
      }),
    );
    setReview(data);
    setStatus("Estimated impact updated.");
    return data;
  }
  async function save(value: Criteria, current: Review) {
    if (locked.current) return;
    locked.current = true;
    setMerging(false);
    setBusy(true);
    setError("");
    lastAttempt.current = serial(value);
    setStatus("Updating estimated impact…");
    try {
      await persist(value, current);
    } catch (failure) {
      await handleFailure(failure);
      setStatus("");
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  useEffect(() => {
    if (
      !draft ||
      !review ||
      busy ||
      conflict ||
      merging ||
      unavailable ||
      completedSearch ||
      uncertain ||
      serial(draft) === serial(review.criteria) ||
      serial(draft) === lastAttempt.current
    )
      return;
    if (
      !draft.groups.length ||
      draft.groups.some(
        (g) => !draft.criteria.some((c) => c.group_id === g.id),
      ) ||
      draft.criteria.some((c) => c.value === "")
    )
      return;
    const timer = window.setTimeout(() => {
      void save(draft, review);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [
    draft,
    review,
    busy,
    conflict,
    merging,
    unavailable,
    completedSearch,
    uncertain,
  ]);
  async function openResults(searchId: string) {
    const transport = workflowTransport(tenant);
    const resultToken = await transport.create(
      "search-results",
      { search_id: searchId, criteria_token: token },
      retryKey.current,
    );
    transport.navigate("search-results", resultToken);
  }
  async function confirm() {
    if (!draft || !review || !token || locked.current || conflict || uncertain)
      return;
    locked.current = true;
    setBusy(true);
    setError("");
    setStatus("Running the confirmed criteria…");
    let executing = false;
    try {
      if (completedSearch) {
        await openResults(completedSearch);
        return;
      }
      const accepted = await persist(draft, review);
      executing = true;
      const response = await request(`/api/v1/tenants/${tenant}/searches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: serial(accepted.criteria),
      });
      // Do not automatically retry execution: this existing endpoint is not idempotent.
      const { data } = await responseJson<{ search_id: string }>(response);
      executing = false;
      setCompletedSearch(data.search_id);
      await openResults(data.search_id);
    } catch (failure) {
      if (
        executing &&
        (!(failure instanceof ApiError) || failure.status >= 500)
      ) {
        setUncertain(true);
        setError(
          "The search outcome could not be confirmed. It will not be submitted again automatically. Return to search to continue safely.",
        );
      } else await handleFailure(failure);
      setStatus("");
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  const change = (value: Criteria) => {
    setDraft(value);
    setError("");
    lastAttempt.current = "";
  };
  return (
    <div
      className="criteria-review-page"
      onClickCapture={(event) => {
        // A fragment-bound handoff must survive keyboard skip-link activation.
        if ((event.target as HTMLElement).closest('a[href="#main"]')) {
          event.preventDefault();
          document.getElementById("main")?.focus();
        }
      }}
    >
      <ReviewFrame
        embedded={Boolean(embeddedToken)}
        title="We read your search as"
        navigation={
          <a href={`/tenants/${tenant}/recruiter/search/`}>Return to search</a>
        }
      >
        <div className="review-shell">
          <p className="review-step">
            {embeddedToken
              ? "RESULTS / ADJUST CRITERIA"
              : "SEARCH / REVIEW / RESULTS"}
          </p>
          <p className="ui-help">
            Structured criteria restored securely. The original prompt is not
            retained here.
          </p>
          {loading && <Loading label="Restoring authorized criteria…" />}
          {error && <Alert>{error}</Alert>}
          {!loading && !review && !unavailable && (
            <Button onClick={() => void load()}>Retry restoration</Button>
          )}
          {!loading && <StatusMessage>{status}</StatusMessage>}
          {conflict && draft && (
            <ConflictPanel
              conflict={{
                current: { criteria: serial(conflict.criteria) },
                attempted: { criteria: serial(draft) },
                changed_fields: ["criteria"],
                current_etag: conflict.etag,
              }}
              onDiscard={() => {
                setReview(conflict);
                setDraft(conflict.criteria);
                setConflict(null);
              }}
              onReview={() => {
                setReview(conflict);
                setConflict(null);
                setMerging(true);
                lastAttempt.current = serial(draft);
                setStatus(
                  "Review your local edits against the stored version. Save explicitly when ready.",
                );
              }}
              onResubmit={() => {
                const current = conflict;
                setConflict(null);
                void save(draft, current);
              }}
            />
          )}
          {draft && review && (
            <form
              className="review-panel"
              onSubmit={(event) => {
                event.preventDefault();
                void confirm();
              }}
            >
              <div className="review-heading">
                <div>
                  <h2>Review before search</h2>
                  <p>
                    Add, edit or remove criteria. Your edits take precedence
                    over suggestions.
                  </p>
                </div>
                <ImpactSummary review={review} />
              </div>
              <p className="ui-help">
                Only server-accepted edits survive refresh. Refresh never runs a
                search. Context:{" "}
                {draft.context.type === "OPENING"
                  ? "Opening-linked search"
                  : "Ad-hoc search"}
                .
              </p>
              <fieldset
                className="review-controls"
                disabled={
                  busy ||
                  Boolean(conflict) ||
                  uncertain ||
                  Boolean(completedSearch)
                }
              >
                <legend className="ui-visually-hidden">
                  Edit search criteria
                </legend>
                {draft.groups.length === 0 && (
                  <EmptyState title="No criteria groups yet">
                    Add a group and at least one criterion before confirming.
                  </EmptyState>
                )}
                {draft.groups.map((group) => (
                  <GroupEditor
                    key={group.id}
                    group={group}
                    draft={draft}
                    review={review}
                    change={change}
                  />
                ))}
                <Button
                  id="add-group"
                  variant="secondary"
                  onClick={() =>
                    change({
                      ...draft,
                      groups: [
                        ...draft.groups,
                        {
                          id: crypto.randomUUID(),
                          label: "Recruiter-defined group",
                          purpose: "REQUIREMENT",
                          operator: "ALL",
                        },
                      ],
                    })
                  }
                >
                  Add group
                </Button>
                <Field label="Maximum results">
                  {(p) => (
                    <TextInput
                      {...p}
                      type="number"
                      min={1}
                      max={100}
                      required
                      value={draft.limit}
                      onChange={(e) =>
                        change({ ...draft, limit: Number(e.target.value) })
                      }
                    />
                  )}
                </Field>
              </fieldset>
              <div className="ui-row">
                <Button
                  type="submit"
                  busy={busy}
                  disabled={
                    Boolean(conflict) || uncertain || !draft.criteria.length
                  }
                >
                  {completedSearch
                    ? "Retry opening results"
                    : "Run confirmed search"}
                </Button>
                {!completedSearch && (
                  <Button
                    variant="secondary"
                    disabled={busy || Boolean(conflict) || uncertain}
                    onClick={() => void save(draft, review)}
                  >
                    Update estimate
                  </Button>
                )}
              </div>
            </form>
          )}
        </div>
      </ReviewFrame>
    </div>
  );
}
