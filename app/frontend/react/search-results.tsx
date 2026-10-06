import { useEffect, useRef, useState } from "react";
import type { PageProps } from "./mount";
import { ResultsFilters } from "./results-filters";
import { ResultIcon } from "./result-icon";
import { CareerJourney } from "./career-journey";
import { CriteriaReview, type Criteria } from "./criteria-review";
import { workflowTransport } from "../shared/workflow-handoff";
import {
  Alert,
  AppShell,
  PlatformNavigation,
  Button,
  Checkbox,
  Chip,
  Dialog,
  EmptyState,
  Loading,
} from "./components";
import { ApiError, responseJson } from "../shared/api-client";
import { handoffToken } from "../shared/workflow-handoff";
import { visualAssets } from "./visual-assets";
import { SparklesCore } from "./components/ui/sparkles";
import {
  CandidateDetail,
  fieldText,
  type SearchItem,
} from "./candidate-detail";

type Results = {
  search_id: string;
  items: SearchItem[];
  next_cursor: string | null;
};
type Selection = { search_id: string; candidate_ids: string[]; etag: string };
function consolidatedFindingMessages(findings: SearchItem["findings"]) {
  const grouped = new Map<string, Set<string>>();
  for (const finding of findings) {
    const records = grouped.get(finding.message) ?? new Set<string>();
    records.add(finding.evidence.employment_record_id);
    grouped.set(finding.message, records);
  }
  return [...grouped.entries()].map(([message, recordIds]) => ({
    message,
    recordCount: recordIds.size,
  }));
}
function fragmentSelection() {
  const value = new URLSearchParams(location.hash.slice(1)).get("selection");
  return value && /^[A-Za-z0-9_-]{43}$/.test(value) ? value : null;
}
export function ResultsToolbar({
  count,
  total,
  selected,
  filter,
  setFilter,
  compare,
  busy,
  filtersOpen,
  toggleFilters,
}: {
  filtersOpen: boolean;
  toggleFilters: () => void;
  count: number;
  total?: number;
  selected: number;
  filter: boolean;
  setFilter: (value: boolean) => void;
  compare: () => void;
  busy: boolean;
}) {
  return (
    <section className="results-toolbar" aria-label="Result controls">
      <span className="ui-visually-hidden" role="status" aria-live="polite">
        {selected} candidates selected for comparison.
      </span>
      <h2>
        Showing {count} of {total ?? count} results
      </h2>
      <div className="results-controls">
        <Button
          variant="secondary"
          disabled={busy || selected < 2}
          onClick={compare}
        >
          Compare ({selected})
        </Button>
        <select
          aria-label="Filter results"
          value={filter ? "employment" : "all"}
          onChange={(event) => setFilter(event.target.value === "employment")}
        >
          <option value="all">All</option>
          <option value="employment">With employment information</option>
        </select>
        <Button
          variant="secondary"
          className="results-filter-toggle"
          aria-label="Show filters"
          aria-expanded={filtersOpen}
          aria-controls="results-filter-panel"
          onClick={toggleFilters}
        >
          <ResultIcon name="filters" />
        </Button>
      </div>
    </section>
  );
}
export function ResultCard({
  item,
  selected,
  busy,
  toggle,
  detail,
  action,
  viewed = false,
  changeStatus,
}: {
  item: SearchItem;
  selected: boolean;
  busy: boolean;
  toggle: (checked: boolean) => void;
  detail: () => void;
  action?: (action: "whatsapp" | "email" | "share") => void;
  viewed?: boolean;
  changeStatus?: (status: string) => void;
}) {
  const summary = item.summary;
  const name = fieldText(summary.name);
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("");
  const statusLabel =
    typeof summary.internal_status === "string"
      ? summary.internal_status
          .replaceAll("_", " ")
          .toLowerCase()
          .replace(/^./, (letter) => letter.toUpperCase())
      : "Status";
  const updated =
    typeof summary.updated_at === "string"
      ? new Date(summary.updated_at)
      : null;
  const daysAgo = updated
    ? Math.max(0, Math.floor((Date.now() - updated.getTime()) / 86400000))
    : NaN;
  const stageSignals = Array.isArray(summary.stage_signals)
    ? summary.stage_signals.filter(
        (signal): signal is string => typeof signal === "string",
      )
    : [];
  const employmentNotices = consolidatedFindingMessages(item.findings);
  const education = Array.isArray(summary.education)
    ? summary.education
        .flatMap((item) =>
          item && typeof item === "object" && "school" in item
            ? [String(item.school)]
            : [],
        )
        .filter(Boolean)
    : [];
  return (
    <article className="result-card">
      <div className="candidate-avatar" aria-hidden="true">
        {initials}
      </div>
      <div className="result-card-main">
        <div className="candidate-title-line">
          <h3>{name}</h3>
          {viewed && <span className="viewed-mark">Viewed</span>}
          {Number.isFinite(daysAgo) && (
            <span className="freshness-pill">
              Updated{" "}
              {daysAgo === 0
                ? "today"
                : `${daysAgo} ${daysAgo === 1 ? "day" : "days"} ago`}
            </span>
          )}
        </div>
        <p className="candidate-headline">
          {fieldText(summary.current_role ?? summary.headline)}
          {summary.current_company
            ? ` at ${fieldText(summary.current_company)}`
            : ""}
        </p>
        {education.length ? (
          <p className="candidate-alias">{education.join(" · ")}</p>
        ) : null}
        <div className="result-facts">
          <div>
            <ResultIcon name="location" /> Location:{" "}
            <b>{fieldText(summary.location)}</b>
          </div>
          <div>
            <ResultIcon name="calendar" /> Notice period:{" "}
            <b>{fieldText(summary.notice_period)}</b>
          </div>
          <div>
            <ResultIcon name="briefcase" /> Experience:{" "}
            <b>{fieldText(summary.experience_years)} years</b>
          </div>
          <div>
            <ResultIcon name="rupee" /> Current salary:{" "}
            <b>{fieldText(summary.current_salary)}</b>
          </div>
        </div>
        <CareerJourney history={summary.employment_history} />
        <div className="result-skills">
          <strong>Skills</strong>
          <div className="skill-chip-list">
            {Array.isArray(summary.skills) &&
              summary.skills.map((skill, index) => (
                <Chip key={index} tone="sage">
                  ✓ {fieldText(skill)}
                </Chip>
              ))}
          </div>
        </div>
      </div>
      <div className="result-card-actions">
        <Checkbox
          label="Compare"
          aria-label={`Compare ${name}`}
          checked={selected}
          disabled={busy}
          onChange={(event) => toggle(event.target.checked)}
        />
        <label className="side-label" htmlFor={`status-${item.candidate_id}`}>
          {statusLabel}
        </label>
        <select
          id={`status-${item.candidate_id}`}
          className="result-status-select"
          value={
            typeof summary.internal_status === "string"
              ? summary.internal_status
              : ""
          }
          disabled={busy || !changeStatus}
          onChange={(event) => changeStatus?.(event.target.value)}
          title="Choose a status to review and save in the profile"
        >
          <option value="">Unavailable</option>
          {[
            "SOURCED",
            "SHORTLISTED",
            "CONTACTED",
            "SCREENING",
            "INTERVIEWING",
            "OFFERED",
            "REJECTED",
            "NOT_RELEVANT",
            "HIRED",
          ].map((status) => (
            <option key={status} value={status}>
              {status
                .replaceAll("_", " ")
                .toLowerCase()
                .replace(/^./, (character) => character.toUpperCase())}
            </option>
          ))}
        </select>
        <div className="candidate-contact-actions">
          <Button
            variant="secondary"
            aria-label={`WhatsApp ${name}`}
            disabled={busy || !action}
            title="Open the consent-checked WhatsApp workflow"
            onClick={() => action?.("whatsapp")}
          >
            <ResultIcon name="whatsapp" />
          </Button>
          <Button
            variant="secondary"
            aria-label={`Email ${name}`}
            disabled={busy || !action}
            title="Open the consent-checked email workflow"
            onClick={() => action?.("email")}
          >
            <ResultIcon name="mail" />
          </Button>
          <Button
            variant="secondary"
            aria-label={`Share ${name}`}
            disabled={busy || !action}
            title="Open the recruiter sharing workflow"
            onClick={() => action?.("share")}
          >
            <ResultIcon name="share" />
          </Button>
          <Button className="view-profile-button" onClick={detail}>
            View profile
          </Button>
        </div>
        {stageSignals.length > 0 && (
          <div className="side-signals">
            <strong>Stage signals</strong>
            <div className="stage-signal-chips">
              {stageSignals.map((signal) => (
                <Chip key={signal} tone="gold">
                  {signal}
                </Chip>
              ))}
            </div>
          </div>
        )}
        {employmentNotices.length > 0 && (
          <div className="side-signals">
            <strong>Employment information</strong>
            {employmentNotices.map((finding) => (
              <Chip key={finding.message} tone="gold">
                {finding.message}
                {finding.recordCount > 1
                  ? ` (${finding.recordCount} separate employment records)`
                  : ""}
              </Chip>
            ))}
          </div>
        )}
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
  const [noSearch, setNoSearch] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [viewedIds, setViewedIds] = useState<string[]>([]);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [requestedStatus, setRequestedStatus] = useState<string | undefined>();
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
    setNoSearch(false);
    try {
      if (!token) {
        const { data: recents } = await responseJson<
          Array<{ search_id: string }>
        >(await request(`/api/v1/tenants/${tenant}/recent-searches`));
        if (current !== generation.current) return;
        if (!recents.length) {
          setNoSearch(true);
          return;
        }
        const restoredToken = await workflowTransport(tenant).create(
          "search-results",
          { search_id: recents[0].search_id },
        );
        if (current !== generation.current) return;
        location.replace(
          `/tenants/${tenant}/recruiter/search/?view=results#handoff=${restoredToken}`,
        );
        return;
      }
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
      className={`search-results-page${filtersOpen ? " has-filters" : ""}`}
      onClickCapture={(event) => {
        if ((event.target as HTMLElement).closest('a[href="#main"]')) {
          event.preventDefault();
          document.getElementById("main")?.focus();
        }
      }}
    >
      <AppShell
        title="Search results"
        navigation={
          <>
            <PlatformNavigation active="results" tenantId={tenant} />
            <span className="results-recruiter">
              <span aria-hidden="true" />
              Recruiter
            </span>
            <Button
              variant="secondary"
              onClick={async () => {
                try {
                  const response = await request("/api/v1/session/sign-out", {
                    method: "DELETE",
                  });
                  if (response.ok) location.replace("/");
                  else setNotice("Sign-out failed. Try again.");
                } catch {
                  setNotice("Sign-out failed. Try again.");
                }
              }}
            >
              Logout
            </Button>
          </>
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
        {noSearch && (
          <EmptyState
            title="Your search results will appear here"
            illustration={{
              src: visualAssets.talentDiscoveryEmpty,
              width: 1024,
              height: 1024,
            }}
          >
            <p>
              Start a search to find candidates. You can return here to your
              latest results.
            </p>
            <a
              className="ui-button"
              href={`/tenants/${tenant}/recruiter/search/`}
            >
              Start a search
            </a>
          </EmptyState>
        )}
        {notice && <Alert tone="gold">{notice}</Alert>}
        {data && (
          <>
            <section
              className="results-sparkles-banner"
              aria-labelledby="results-sparkles-title"
            >
              <div className="results-sparkles-field" aria-hidden="true">
                <SparklesCore
                  id="results-sparkles"
                  background="transparent"
                  minSize={0.4}
                  maxSize={1.15}
                  particleDensity={110}
                  particleColor="#ffffff"
                  speed={0.45}
                />
              </div>
              <div className="results-sparkles-beam" aria-hidden="true" />
              <div className="results-sparkles-copy">
                <span>Authorized talent discovery</span>
                <h2 id="results-sparkles-title">Talent matches</h2>
                <p>
                  {data.items.length} candidate
                  {data.items.length === 1 ? "" : "s"} available in this search
                </p>
              </div>
            </section>
            <details
              id="results-criteria"
              aria-label="Applied deterministic criteria"
            >
              <summary>Applied criteria</summary>
              <Button
                id="refresh-results"
                variant="secondary"
                disabled={busy}
                onClick={() => void load()}
              >
                Refresh authorized results
              </Button>
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
            </details>
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
            <div className="results-workspace">
              <div className="results-main-column">
                <ResultsToolbar
                  filtersOpen={filtersOpen}
                  toggleFilters={() => setFiltersOpen((value) => !value)}
                  count={shown.length}
                  total={data.items.length}
                  selected={selection?.candidate_ids.length ?? 0}
                  filter={filter}
                  setFilter={setFilter}
                  busy={busy}
                  compare={() => {
                    if (selectionToken.current)
                      location.assign(
                        `/tenants/${tenant}/recruiter/comparison/#handoff=${selectionToken.current}`,
                      );
                  }}
                />
                {!data.items.length ? (
                  <EmptyState
                    title="No authorized candidates matched"
                    illustration={{
                      src: visualAssets.talentDiscoveryEmpty,
                      width: 1024,
                      height: 1024,
                    }}
                  >
                    Broaden deterministic criteria or choose another active
                    opening.
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
                          (
                            pendingSelection ?? selection?.candidate_ids
                          )?.includes(item.candidate_id) ?? false
                        }
                        busy={busy || selectionBlocked}
                        toggle={(checked) =>
                          void toggle(item.candidate_id, checked)
                        }
                        viewed={viewedIds.includes(item.candidate_id)}
                        changeStatus={(status) => {
                          setRequestedStatus(status);
                          setDetailId(item.candidate_id);
                        }}
                        action={(action) => {
                          location.assign(
                            `/tenants/${tenant}/recruiter/candidates/${item.candidate_id}/?search_id=${encodeURIComponent(data.search_id)}&action=${action}#disclosure`,
                          );
                        }}
                        detail={() => {
                          setRequestedStatus(undefined);
                          setDetailId(item.candidate_id);
                          setViewedIds((current) =>
                            current.includes(item.candidate_id)
                              ? current
                              : [...current, item.candidate_id],
                          );
                        }}
                      />
                    ))}
                  </div>
                )}
                {data.next_cursor && (
                  <Button busy={busy} onClick={() => void more()}>
                    Load more
                  </Button>
                )}
              </div>
              {filtersOpen && (
                <ResultsFilters
                  criteria={criteria}
                  tenant={tenant}
                  request={request}
                  count={data.items.length}
                  onClose={() => {
                    setFiltersOpen(false);
                    requestAnimationFrame(() =>
                      document
                        .querySelector<HTMLButtonElement>(
                          ".results-filter-toggle",
                        )
                        ?.focus(),
                    );
                  }}
                />
              )}
            </div>
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
                  key={detailId}
                  initialStatus={requestedStatus}
                  onWorkUpdated={(status) =>
                    setData((current) =>
                      current
                        ? {
                            ...current,
                            items: current.items.map((item) =>
                              item.candidate_id === detailId
                                ? {
                                    ...item,
                                    summary: {
                                      ...item.summary,
                                      internal_status: status,
                                    },
                                  }
                                : item,
                            ),
                          }
                        : current,
                    )
                  }
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
