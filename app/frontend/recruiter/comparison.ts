import { escapeText } from "./candidate-findings";
import { workflowTransport, handoffToken } from "../shared/workflow-handoff";

export const COMPARISON_SELECTION_KEY = "enter.comparison-selection.v1";
let currentSelection: ComparisonSelection | null = null;
let selectionToken: string | null = null;
let selectionEtag = "";

export type ComparisonSelection = {
  tenant_id: string;
  context_type: "SEARCH" | "OPENING" | "SHORTLIST";
  context_id: string;
  candidate_ids: string[];
};

type ComparisonField = {
  state: "KNOWN" | "UNKNOWN" | "UNAVAILABLE";
  value: unknown;
  provenance: string[];
};

type ComparisonCandidate = {
  candidate_id: string;
  permitted_fields: Record<string, ComparisonField>;
  findings: { code: string; informational_only: boolean; message: string }[];
  unknowns: string[];
};

type ComparisonResult = {
  fields: string[];
  candidates: ComparisonCandidate[];
};

export function readComparisonSelection(): ComparisonSelection | null {
  return currentSelection
    ? {
        ...currentSelection,
        candidate_ids: [...currentSelection.candidate_ids],
      }
    : null;
}

export async function writeComparisonSelection(
  value: ComparisonSelection,
): Promise<void> {
  const transport = workflowTransport(value.tenant_id);
  if (!selectionToken || currentSelection?.context_id !== value.context_id) {
    selectionToken = await transport.create("comparison-selection", {
      search_id: value.context_id,
      candidate_ids: value.candidate_ids,
    });
    const restored = await transport.restore<{ etag: string }>(
      "comparison-selection",
      selectionToken,
    );
    selectionEtag = restored.etag;
  } else {
    const response = await transport.client(
      `/api/v1/tenants/${value.tenant_id}/search-handoffs/comparison-selection`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-Workflow-Handoff": selectionToken,
          "If-Match": selectionEtag,
        },
        body: JSON.stringify({ candidate_ids: value.candidate_ids }),
      },
    );
    if (!response.ok)
      throw new Error(
        "Selection changed or is unavailable. Refresh before trying again.",
      );
    selectionEtag = ((await response.json()) as { etag: string }).etag;
  }
  currentSelection = { ...value, candidate_ids: [...value.candidate_ids] };
  if (document.querySelector("[data-recruiter-search]")) {
    const fragment = new URLSearchParams(location.hash.slice(1));
    fragment.set("selection", selectionToken!);
    history.replaceState(
      null,
      "",
      `${location.pathname}${location.search}#${fragment}`,
    );
  }
}

export function comparisonDestination(tenantId: string): string {
  if (!selectionToken) throw new Error("Selection is unavailable");
  return `/tenants/${tenantId}/recruiter/comparison/#handoff=${selectionToken}`;
}

async function restoreSelection(
  tenantId: string,
): Promise<ComparisonSelection | null> {
  selectionToken = handoffToken();
  if (!selectionToken) return null;
  const state = await workflowTransport(tenantId).restore<{
    search_id: string;
    candidate_ids: string[];
    etag: string;
  }>("comparison-selection", selectionToken);
  selectionEtag = state.etag;
  currentSelection = {
    tenant_id: tenantId,
    context_type: "SEARCH",
    context_id: state.search_id,
    candidate_ids: state.candidate_ids,
  };
  return readComparisonSelection();
}

export async function restoreSearchSelection(
  tenantId: string,
  searchId: string,
): Promise<void> {
  const token = new URLSearchParams(location.hash.slice(1)).get("selection");
  if (!token || !/^[A-Za-z0-9_-]{43}$/.test(token)) return;
  const state = await workflowTransport(tenantId).restore<{
    search_id: string;
    candidate_ids: string[];
    etag: string;
  }>("comparison-selection", token);
  if (state.search_id !== searchId)
    throw new Error("Selection context changed");
  selectionToken = token;
  selectionEtag = state.etag;
  currentSelection = {
    tenant_id: tenantId,
    context_type: "SEARCH",
    context_id: searchId,
    candidate_ids: state.candidate_ids,
  };
}

function csrfToken(): string {
  return (
    document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? ""
  );
}

function labelFor(field: string): string {
  return field
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function displayValue(value: unknown): string[] {
  if (value === null || value === undefined || value === "") return [];
  if (Array.isArray(value)) {
    return value.flatMap((item) => {
      if (typeof item !== "object" || item === null) return [String(item)];
      const record = item as Record<string, unknown>;
      const role = record.role_title || "Role unknown";
      const company = record.company || "Company unknown";
      const start = record.start_date || "Start unknown";
      const end = record.is_current
        ? "Current"
        : record.end_date || "End unknown";
      return [`${role} — ${company} (${start} to ${end})`];
    });
  }
  if (typeof value === "object") return [JSON.stringify(value)];
  return [String(value)];
}

function fieldContent(field: ComparisonField): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = `comparison-value comparison-value--${field.state.toLowerCase()}`;
  if (field.state === "UNKNOWN") {
    wrapper.textContent = "Unknown";
    return wrapper;
  }
  if (field.state === "UNAVAILABLE") {
    wrapper.textContent = "Unavailable";
    return wrapper;
  }
  const values = displayValue(field.value);
  if (!values.length) {
    wrapper.textContent = "None recorded";
  } else if (values.length === 1) {
    wrapper.textContent = values[0];
  } else {
    const list = document.createElement("ul");
    values.forEach((value) => {
      const item = document.createElement("li");
      item.textContent = value;
      list.append(item);
    });
    wrapper.append(list);
  }
  if (field.provenance.length) {
    const provenance = document.createElement("small");
    provenance.textContent = `Evidence: ${field.provenance.join(", ")}`;
    wrapper.append(provenance);
  }
  return wrapper;
}

function candidateName(candidate: ComparisonCandidate): string {
  const name = candidate.permitted_fields.name;
  return name?.state === "KNOWN" && typeof name.value === "string"
    ? name.value
    : "Candidate";
}

function renderCandidate(
  candidate: ComparisonCandidate,
  fields: string[],
): HTMLElement {
  const card = document.createElement("article");
  card.className = "comparison-card";
  card.dataset.candidateId = candidate.candidate_id;
  const heading = document.createElement("h3");
  heading.textContent = candidateName(candidate);
  card.append(heading);
  const remove = document.createElement("button");
  remove.type = "button";
  remove.dataset.removeCandidate = candidate.candidate_id;
  remove.textContent = `Remove ${candidateName(candidate)}`;
  card.append(remove);
  const details = document.createElement("dl");
  fields.forEach((name) => {
    const term = document.createElement("dt");
    term.textContent = labelFor(name);
    const description = document.createElement("dd");
    description.append(fieldContent(candidate.permitted_fields[name]));
    details.append(term, description);
  });
  card.append(details);
  candidate.findings.forEach((finding) => {
    const aside = document.createElement("div");
    aside.setAttribute("role", "group");
    aside.className = "finding";
    aside.setAttribute("aria-label", "Informational employment finding");
    aside.innerHTML = `<strong>${escapeText(finding.code)}</strong><p>${escapeText(finding.message)}</p><p>${escapeText(finding.code)} is informational only and does not affect ordering or scores.</p>`;
    card.append(aside);
  });
  return card;
}

const root = document.querySelector<HTMLElement>("[data-comparison]");
if (root) {
  const status = root.querySelector<HTMLElement>("[data-comparison-status]")!;
  const empty = root.querySelector<HTMLElement>("[data-comparison-empty]")!;
  const content = root.querySelector<HTMLElement>("[data-comparison-content]")!;
  const candidates = root.querySelector<HTMLElement>(
    "[data-comparison-candidates]",
  )!;
  let selection = readComparisonSelection();

  const showEmpty = (message?: string) => {
    empty.hidden = false;
    content.hidden = true;
    if (message) status.textContent = message;
  };

  const render = (result: ComparisonResult) => {
    candidates.replaceChildren();
    result.candidates.forEach((candidate) =>
      candidates.append(renderCandidate(candidate, result.fields)),
    );
    empty.hidden = true;
    content.hidden = false;
  };

  const load = async () => {
    try {
      selection = await restoreSelection(root.dataset.tenantId!);
      if (
        !selection ||
        selection.tenant_id !== root.dataset.tenantId ||
        selection.candidate_ids.length < 2
      ) {
        showEmpty("No comparison request was made.");
        return;
      }
      status.textContent = "Rechecking current candidate access…";
      const response = await fetch(
        `/api/v1/tenants/${selection.tenant_id}/comparisons`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken(),
            "X-Tenant-ID": selection.tenant_id,
            "Idempotency-Key": crypto.randomUUID(),
          },
          credentials: "same-origin",
          body: JSON.stringify({
            candidate_ids: selection.candidate_ids,
            context_type: selection.context_type,
            context_id: selection.context_id,
          }),
        },
      );
      if (!response.ok) {
        showEmpty(
          "Comparison is unavailable. Return to results and try again.",
        );
        return;
      }
      const result = (await response.json()) as ComparisonResult;
      const allowed = new Set(
        result.candidates.map((item) => item.candidate_id),
      );
      const removed = selection.candidate_ids.length - allowed.size;
      selection.candidate_ids = selection.candidate_ids.filter((id) =>
        allowed.has(id),
      );
      await writeComparisonSelection(selection);
      if (!result.candidates.length) {
        showEmpty(
          "Selected candidates are no longer available in this context.",
        );
        return;
      }
      render(result);
      status.textContent = removed
        ? `${removed} selected candidate${removed === 1 ? " is" : "s are"} no longer available. The comparison was updated.`
        : `${result.candidates.length} currently authorized candidates loaded.`;
    } catch {
      showEmpty(
        "Selection expired, changed or is unavailable. Return to search.",
      );
    }
  };

  candidates.addEventListener("click", async (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>(
      "[data-remove-candidate]",
    );
    if (!button || !selection) return;
    const controls = [
      ...candidates.querySelectorAll<HTMLButtonElement>(
        "[data-remove-candidate]",
      ),
    ];
    const index = controls.indexOf(button);
    const next = {
      ...selection,
      candidate_ids: selection.candidate_ids.filter(
        (id) => id !== button.dataset.removeCandidate,
      ),
    };
    try {
      await writeComparisonSelection(next);
      selection = next;
    } catch {
      status.textContent =
        "Selection changed or is unavailable. Refresh before trying again.";
      return;
    }
    button.closest(".comparison-card")?.remove();
    status.textContent = `${selection.candidate_ids.length} candidate${selection.candidate_ids.length === 1 ? " remains" : "s remain"} selected.`;
    const remaining = [
      ...candidates.querySelectorAll<HTMLButtonElement>(
        "[data-remove-candidate]",
      ),
    ];
    (remaining[index] ?? remaining[index - 1] ?? content).focus();
  });

  root
    .querySelector<HTMLButtonElement>("[data-close-comparison]")
    ?.addEventListener("click", async () => {
      const tenant = root.dataset.tenantId!;
      try {
        if (!selectionToken) throw new Error("No context");
        const response = await workflowTransport(tenant).client(
          `/api/v1/tenants/${tenant}/search-handoffs/comparison-selection/return`,
          {
            method: "POST",
            headers: {
              "X-Workflow-Handoff": selectionToken,
              "Idempotency-Key": crypto.randomUUID(),
            },
          },
        );
        if (!response.ok) throw new Error("Return unavailable");
        location.assign(
          ((await response.json()) as { return_path: string }).return_path,
        );
      } catch {
        location.assign(`/tenants/${tenant}/recruiter/search/`);
      }
    });
  void load();
}

function restoreComparisonFocus(): void {
  if (new URLSearchParams(location.search).get("view") !== "results") return;
  const invoker = document.querySelector<HTMLButtonElement>(
    "[data-open-comparison]",
  );
  if (!invoker) return;
  invoker.focus();
}
window.addEventListener("pageshow", () =>
  window.setTimeout(restoreComparisonFocus, 0),
);
window.setTimeout(restoreComparisonFocus, 0);
