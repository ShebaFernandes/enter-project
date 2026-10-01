import { useEffect, useRef, useState } from "react";
import type { PageProps } from "./mount";
import { CriteriaReview, type Criteria } from "./criteria-review";
import { workflowTransport } from "../shared/workflow-handoff";
import {
  Alert,
  AppShell,
  Button,
  Checkbox,
  Chip,
  Dialog,
  EmptyState,
  Loading,
  StatusMessage,
} from "./components";
import { ApiError, responseJson } from "../shared/api-client";
import { handoffToken } from "../shared/workflow-handoff";
import {
  CandidateDetail,
  Evidence,
  Finding,
  fieldText,
  type SearchItem,
} from "./candidate-detail";

type Results = {
  search_id: string;
  items: SearchItem[];
  next_cursor: string | null;
};
type Selection = { search_id: string; candidate_ids: string[]; etag: string };
function fragmentSelection() {
  const value = new URLSearchParams(location.hash.slice(1)).get("selection");
  return value && /^[A-Za-z0-9_-]{43}$/.test(value) ? value : null;
}
export function ResultsToolbar({
  count,
  selected,
  filter,
  setFilter,
  refresh,
  compare,
  busy,
}: {
  count: number;
  selected: number;
  filter: boolean;
  setFilter: (value: boolean) => void;
  refresh: () => void;
  compare: () => void;
  busy: boolean;
}) {
  return (
    <section className="results-toolbar" aria-label="Result controls">
      <div>
        <h2>Search results</h2>
        <p>
          {count} currently authorized result(s). Server ordering is preserved.
        </p>
      </div>
      <div className="ui-row">
        <Button
          variant="secondary"
          aria-pressed={!filter}
          onClick={() => setFilter(false)}
        >
          All candidates
        </Button>
        <Button
          variant="secondary"
          aria-pressed={filter}
          onClick={() => setFilter(true)}
        >
          With employment information
        </Button>
      </div>
      <p className="ui-help">
        Display filter only; informational findings never change search scores
        or order.
      </p>
      <div className="ui-row">
        <Button
          id="refresh-results"
          variant="secondary"
          disabled={busy}
          onClick={refresh}
        >
          Refresh authorized results
        </Button>
        <Button disabled={busy || selected < 2} onClick={compare}>
          Compare selected candidates
        </Button>
      </div>
      <StatusMessage>
        {selected} candidates selected for comparison.
      </StatusMessage>
    </section>
  );
}
export function ResultCard({
  item,
  selected,
  busy,
  toggle,
  detail,
}: {
  item: SearchItem;
  selected: boolean;
  busy: boolean;
  toggle: (checked: boolean) => void;
  detail: () => void;
}) {
  return (
    <article className="result-card">
      <div className="result-card-heading">
        <div>
          <h3>{fieldText(item.summary.name)}</h3>
          <p>{fieldText(item.summary.current_role ?? item.summary.headline)}</p>
        </div>
        <Chip>{fieldText(item.summary.location)}</Chip>
      </div>
      <p>Experience: {fieldText(item.summary.experience_years)}</p>
      <div className="ui-row">
        {Array.isArray(item.summary.skills) &&
          item.summary.skills.map((skill, index) => (
            <Chip key={index} tone="sage">
              {fieldText(skill)}
            </Chip>
          ))}
      </div>
      <Evidence items={item.evidence} />
      {item.unknowns.length > 0 && (
        <p>
          Unknown:{" "}
          {item.unknowns.map((field) => field.replaceAll("_", " ")).join(", ")}
        </p>
      )}
      {item.findings.map((finding, index) => (
        <Finding key={index} finding={finding} />
      ))}
      <div className="result-card-actions">
        <Checkbox
          label={`Compare ${fieldText(item.summary.name)}`}
          checked={selected}
          disabled={busy}
          onChange={(event) => toggle(event.target.checked)}
        />
        <Button variant="secondary" onClick={detail}>
          View authorized details
        </Button>
      </div>
    </article>
  );
}

export function SearchResults({ bootstrap, request }: PageProps) {
  const tenant = bootstrap.tenantId ?? "";
  const [token] = useState(handoffToken);
  const base = `/api/v1/tenants/${tenant}/search-handoffs`;
  const [data, setData] = useState<Results | null>(null);
  const [criteria, setCriteria] = useState<Criteria | null>(null);
  const [editToken, setEditToken] = useState<string | null>(null);
  const editRetry = useRef(crypto.randomUUID());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [pendingSelection, setPendingSelection] = useState<string[] | null>(
    null,
  );
  const [selectionBlocked, setSelectionBlocked] = useState(false);
  const selectionToken = useRef(fragmentSelection());
  const locked = useRef(false);
  const generation = useRef(0);
  const selectionRetry = useRef(crypto.randomUUID());
  const pageRetry = useRef(crypto.randomUUID());
  const read = async <T,>(path: string, bearer: string) =>
    (
      await responseJson<T>(
        await request(path, { headers: { "X-Workflow-Handoff": bearer } }),
      )
    ).data;
  const failureText = (failure: unknown) =>
    failure instanceof ApiError && failure.status === 429
      ? "Too many requests. Wait before refreshing."
      : "Results expired, were revoked or are unavailable for this session. Return to search or retry current access.";
  async function load() {
    const current = ++generation.current;
    setLoading(true);
    setData(null);
    setCriteria(null);
    setEditToken(null);
    setSelection(null);
    setDetailId(null);
    setError("");
    setNotice("");
    setSelectionBlocked(false);
    try {
      if (!token) throw new ApiError(404, null);
      const metadata = await read<{ criteria?: Criteria }>(
        `${base}/search-results`,
        token,
      );
      const restored = await read<Results>(
        `${base}/search-results/display`,
        token,
      );
      let chosen: Selection | null = null;
      if (selectionToken.current) {
        try {
          chosen = await read<Selection>(
            `${base}/comparison-selection`,
            selectionToken.current,
          );
          if (chosen.search_id !== restored.search_id)
            throw new Error("Context changed");
        } catch {
          chosen = null;
          if (current === generation.current) {
            setSelectionBlocked(true);
            setNotice(
              "Previous selection is unavailable. Refresh current access or start a new search; no selection was overwritten.",
            );
          }
        }
      }
      if (current === generation.current) {
        setData(restored);
        setCriteria(metadata.criteria ?? null);
        setSelection(chosen);
      }
    } catch (failure) {
      if (current === generation.current) setError(failureText(failure));
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }
  useEffect(() => {
    void load();
    const hash = () => {
      if (handoffToken() !== token) location.reload();
    };
    const visibility = () => {
      if (document.hidden) {
        generation.current++;
        setData(null);
        setDetailId(null);
        setSelection(null);
      } else void load();
    };
    window.addEventListener("hashchange", hash);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      generation.current++;
      window.removeEventListener("hashchange", hash);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, []);
  async function toggle(candidateId: string, checked: boolean) {
    if (!data || locked.current || selectionBlocked) return;
    const current = generation.current;
    const ids = [...(selection?.candidate_ids ?? [])];
    if (checked && ids.length >= 10) {
      setNotice("You can compare at most 10 candidates.");
      return;
    }
    const next = checked
      ? [...ids, candidateId]
      : ids.filter((id) => id !== candidateId);
    setPendingSelection(next);
    locked.current = true;
    setBusy(true);
    setNotice("");
    try {
      if (!selectionToken.current) {
        const { data: created } = await responseJson<{ token: string }>(
          await request(`${base}/comparison-selection`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Idempotency-Key": selectionRetry.current,
            },
            body: JSON.stringify({
              search_id: data.search_id,
              candidate_ids: next,
            }),
          }),
        );
        selectionToken.current = created.token;
        const fragment = new URLSearchParams(location.hash.slice(1));
        fragment.set("selection", created.token);
        history.replaceState(
          null,
          "",
          `${location.pathname}${location.search}#${fragment}`,
        );
        const restored = await read<Selection>(
          `${base}/comparison-selection`,
          created.token,
        );
        if (current !== generation.current) return;
        setSelection(restored);
      } else {
        const { data: updated } = await responseJson<Selection>(
          await request(`${base}/comparison-selection`, {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
              "X-Workflow-Handoff": selectionToken.current,
              "If-Match": selection?.etag ?? "",
            },
            body: JSON.stringify({ candidate_ids: next }),
          }),
        );
        if (current !== generation.current) return;
        setSelection(updated);
      }
      const fragment = new URLSearchParams(location.hash.slice(1));
      fragment.set("selection", selectionToken.current!);
      history.replaceState(
        null,
        "",
        `${location.pathname}${location.search}#${fragment}`,
      );
    } catch {
      if (current !== generation.current) return;
      setSelectionBlocked(true);
      setSelection(null);
      setNotice(
        "Selection changed or is unavailable. Refresh authorized results before trying again; nothing was silently overwritten.",
      );
    } finally {
      locked.current = false;
      setPendingSelection(null);
      setBusy(false);
    }
  }
  async function more() {
    if (!token || locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      const { data: created } = await responseJson<{ token: string }>(
        await request(`${base}/search-results/page`, {
          method: "POST",
          headers: {
            "X-Workflow-Handoff": token,
            "Idempotency-Key": pageRetry.current,
          },
        }),
      );
      const fragment = new URLSearchParams({ handoff: created.token });
      if (selectionToken.current)
        fragment.set("selection", selectionToken.current);
      location.assign(
        `/tenants/${tenant}/recruiter/search/?view=results#${fragment}`,
      );
    } catch (failure) {
      setData(null);
      setSelection(null);
      setError(failureText(failure));
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  const shown =
    data?.items.filter((item) => !filter || item.findings.length > 0) ?? [];
  return (
    <div
      className="search-results-page"
      onClickCapture={(event) => {
        if ((event.target as HTMLElement).closest('a[href="#main"]')) {
          event.preventDefault();
          document.getElementById("main")?.focus();
        }
      }}
    >
      <AppShell
        title="Candidates for your search"
        navigation={
          <a href={`/tenants/${tenant}/recruiter/search/`}>Return to search</a>
        }
      >
        {loading && <Loading label="Restoring current authorized results…" />}
        {error && (
          <Alert>
            {error}
            <Button onClick={() => void load()}>
              Retry authorized results
            </Button>
          </Alert>
        )}
        {notice && <Alert tone="gold">{notice}</Alert>}
        {data && (
          <>
            <section aria-label="Applied deterministic criteria">
              <h2>Applied criteria</h2>
              {criteria ? (
                criteria.groups.map((group) => (
                  <div key={group.id}>
                    <p>
                      {group.purpose} · {group.operator}
                    </p>
                    <div className="ui-row">
                      {criteria.criteria
                        .filter((item) => item.group_id === group.id)
                        .map((item) => (
                          <Chip key={item.id}>
                            {item.field.replaceAll("_", " ")} {item.operator}{" "}
                            {String(item.value)}
                          </Chip>
                        ))}
                    </div>
                  </div>
                ))
              ) : (
                <p>
                  Applied criteria are currently unavailable. Refresh current
                  access.
                </p>
              )}
              <Button
                id="adjust-criteria"
                variant="secondary"
                disabled={busy || !criteria}
                onClick={() => {
                  setBusy(true);
                  void workflowTransport(tenant)
                    .create(
                      "criteria-review",
                      { search_id: data.search_id },
                      editRetry.current,
                    )
                    .then((handoff) => setEditToken(handoff))
                    .catch(() =>
                      setNotice(
                        "Criteria could not be restored. No search was executed. Refresh current access.",
                      ),
                    )
                    .finally(() => setBusy(false));
                }}
              >
                Adjust criteria
              </Button>
            </section>
            <Dialog
              open={Boolean(editToken)}
              title="Adjust applied criteria"
              onClose={() => {
                setEditToken(null);
                editRetry.current = crypto.randomUUID();
                requestAnimationFrame(() =>
                  document.getElementById("adjust-criteria")?.focus(),
                );
              }}
            >
              {editToken && (
                <CriteriaReview
                  bootstrap={bootstrap}
                  request={request}
                  embeddedToken={editToken}
                />
              )}
            </Dialog>
            <ResultsToolbar
              count={data.items.length}
              selected={selection?.candidate_ids.length ?? 0}
              filter={filter}
              setFilter={setFilter}
              refresh={() => void load()}
              busy={busy}
              compare={() => {
                if (selectionToken.current)
                  location.assign(
                    `/tenants/${tenant}/recruiter/comparison/#handoff=${selectionToken.current}`,
                  );
              }}
            />
            {!data.items.length ? (
              <EmptyState title="No authorized candidates matched">
                Broaden deterministic criteria or choose another active opening.
              </EmptyState>
            ) : !shown.length ? (
              <EmptyState title="No cards in this display filter">
                Choose All candidates to see the unchanged result set.
              </EmptyState>
            ) : (
              <div className="results-grid">
                {shown.map((item) => (
                  <ResultCard
                    key={item.candidate_id}
                    item={item}
                    selected={
                      (pendingSelection ?? selection?.candidate_ids)?.includes(
                        item.candidate_id,
                      ) ?? false
                    }
                    busy={busy || selectionBlocked}
                    toggle={(checked) =>
                      void toggle(item.candidate_id, checked)
                    }
                    detail={() => setDetailId(item.candidate_id)}
                  />
                ))}
              </div>
            )}
            {data.next_cursor && (
              <Button busy={busy} onClick={() => void more()}>
                Load more
              </Button>
            )}
            <Dialog
              open={Boolean(detailId)}
              title="Authorized candidate details"
              onClose={() => {
                if (!data.items.some((item) => item.candidate_id === detailId))
                  requestAnimationFrame(() =>
                    document.getElementById("refresh-results")?.focus(),
                  );
                setDetailId(null);
              }}
            >
              {detailId && (
                <CandidateDetail
                  tenantId={tenant}
                  candidateId={detailId}
                  searchId={data.search_id}
                  request={request}
                  onUnavailable={() => {
                    setData((current) =>
                      current
                        ? {
                            ...current,
                            items: current.items.filter(
                              (item) => item.candidate_id !== detailId,
                            ),
                          }
                        : null,
                    );
                    setSelection(null);
                    setSelectionBlocked(true);
                    setNotice(
                      "Candidate access changed. Refresh current authorization before comparing.",
                    );
                  }}
                />
              )}
            </Dialog>
          </>
        )}
      </AppShell>
    </div>
  );
}
