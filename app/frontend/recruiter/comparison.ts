import { escapeText } from "./candidate-findings";

export const COMPARISON_SELECTION_KEY = "enter.comparison-selection.v1";
const RETURN_FOCUS_KEY = "enter.comparison-return-focus.v1";

export type ComparisonSelection = {
  tenant_id: string;
  context_type: "SEARCH" | "OPENING" | "SHORTLIST";
  context_id: string;
  candidate_ids: string[];
  return_url?: string;
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
  try {
    const value = JSON.parse(
      sessionStorage.getItem(COMPARISON_SELECTION_KEY) ?? "null",
    ) as ComparisonSelection | null;
    if (
      !value ||
      !value.tenant_id ||
      !value.context_id ||
      !Array.isArray(value.candidate_ids)
    )
      return null;
    return { ...value, candidate_ids: [...new Set(value.candidate_ids)] };
  } catch {
    sessionStorage.removeItem(COMPARISON_SELECTION_KEY);
    return null;
  }
}

export function writeComparisonSelection(value: ComparisonSelection): void {
  sessionStorage.setItem(COMPARISON_SELECTION_KEY, JSON.stringify(value));
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
    selection = readComparisonSelection();
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
      showEmpty("Comparison is unavailable. Return to results and try again.");
      return;
    }
    const result = (await response.json()) as ComparisonResult;
    const allowed = new Set(result.candidates.map((item) => item.candidate_id));
    const removed = selection.candidate_ids.length - allowed.size;
    selection.candidate_ids = selection.candidate_ids.filter((id) =>
      allowed.has(id),
    );
    writeComparisonSelection(selection);
    if (!result.candidates.length) {
      showEmpty("Selected candidates are no longer available in this context.");
      return;
    }
    render(result);
    status.textContent = removed
      ? `${removed} selected candidate${removed === 1 ? " is" : "s are"} no longer available. The comparison was updated.`
      : `${result.candidates.length} currently authorized candidates loaded.`;
  };

  candidates.addEventListener("click", (event) => {
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
    selection.candidate_ids = selection.candidate_ids.filter(
      (id) => id !== button.dataset.removeCandidate,
    );
    writeComparisonSelection(selection);
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
    ?.addEventListener("click", () => {
      sessionStorage.setItem(RETURN_FOCUS_KEY, "true");
      if (history.length > 1) history.back();
      else if (selection?.return_url) location.assign(selection.return_url);
    });
  void load();
}

function restoreComparisonFocus(): void {
  if (sessionStorage.getItem(RETURN_FOCUS_KEY) !== "true") return;
  const invoker = document.querySelector<HTMLButtonElement>(
    "[data-open-comparison]",
  );
  if (!invoker) return;
  invoker.focus();
  window.setTimeout(() => sessionStorage.removeItem(RETURN_FOCUS_KEY), 250);
}
window.addEventListener("pageshow", () =>
  window.setTimeout(restoreComparisonFocus, 0),
);
window.setTimeout(restoreComparisonFocus, 0);
