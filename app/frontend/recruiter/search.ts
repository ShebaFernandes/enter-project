import {
  escapeText,
  findingMarkup,
  type CandidateFinding,
} from "./candidate-findings";

type SearchItem = {
  candidate_id: string;
  summary: Record<string, unknown>;
  evidence: { field: string }[];
  findings: CandidateFinding[];
  unknowns: string[];
};
type SearchResponse = {
  search_id: string;
  next_cursor: string | null;
  items: SearchItem[];
};
type InterpretationResponse = {
  original_prompt: string;
  criteria: Record<string, unknown>;
  requires_review: boolean;
  ambiguities: string[];
  estimated_count: number;
};
const root = document.querySelector<HTMLElement>("[data-recruiter-search]");
const REVIEW_KEY = "enter.criteria-review.v1";
const RESULT_KEY = "enter.confirmed-search.v1";

function csrfToken() {
  return (
    document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? ""
  );
}
function criterionRow() {
  const groupId = crypto.randomUUID();
  const row = document.createElement("fieldset");
  row.dataset.groupId = groupId;
  row.dataset.criterionId = crypto.randomUUID();
  row.innerHTML = `<legend>Criterion</legend><label>Purpose <select name="purpose"><option>REQUIREMENT</option><option>PREFERENCE</option><option>EXCLUSION</option></select></label><label>Match <select name="group_operator"><option>ALL</option><option>ANY</option></select></label><label>Field <select name="field"><option value="skill">Skill</option><option value="experience_years">Experience</option><option value="location">Location</option><option value="work_arrangement">Work arrangement</option><option value="availability_date">Availability</option><option value="role_category">Role category</option></select></label><label>Operator <select name="operator"><option>CONTAINS</option><option>EQ</option><option>GTE</option><option>LTE</option></select></label><label>Value <input name="value"></label><button type="button">Remove</button>`;
  row.querySelector("button")?.addEventListener("click", () => row.remove());
  return row;
}
function readCriteria(container: HTMLElement) {
  return [...container.querySelectorAll<HTMLElement>("fieldset")].map((row) => {
    const value = (name: string) =>
      row.querySelector<HTMLSelectElement | HTMLInputElement>(`[name=${name}]`)!
        .value;
    const group = {
      id: row.dataset.groupId!,
      purpose: value("purpose"),
      operator: value("group_operator"),
      label: value("field"),
    };
    return {
      group,
      criterion: {
        id: row.dataset.criterionId!,
        group_id: group.id,
        field: value("field"),
        operator: value("operator"),
        value: value("value"),
      },
    };
  });
}
function card(item: SearchItem, searchId: string) {
  const article = document.createElement("article");
  article.className = "candidate-card";
  article.dataset.findings = String(item.findings.length);
  const summary = item.summary;
  article.innerHTML = `<h3>${escapeText(String(summary.name ?? "Candidate"))}</h3><p>${escapeText(String(summary.current_role ?? summary.headline ?? "Role not provided"))}</p><p>${escapeText(String((summary.location as Record<string, string>)?.display ?? "Location not provided"))}</p><p>${item.evidence.length} matching evidence item(s)</p>${item.findings.map(findingMarkup).join("")}<button type="button">View authorized details</button>`;
  article
    .querySelector("button")
    ?.addEventListener("click", () => openDetail(item.candidate_id, searchId));
  return article;
}
async function openDetail(candidateId: string, searchId: string) {
  if (!root) return;
  const response = await fetch(
    `/api/v1/tenants/${root.dataset.tenantId}/candidates/${candidateId}?search_id=${searchId}`,
    {
      headers: { "X-Tenant-ID": root.dataset.tenantId! },
      credentials: "same-origin",
    },
  );
  if (!response.ok) return;
  const data = await response.json();
  const dialog = root.querySelector<HTMLDialogElement>(
    "[data-candidate-dialog]",
  )!;
  root.querySelector<HTMLElement>("[data-detail]")!.innerHTML =
    `<p>${escapeText(String(data.permitted_fields.name ?? "Candidate"))}</p>${data.findings.map(findingMarkup).join("")}`;
  window.dispatchEvent(
    new CustomEvent("recruiter-search-selection", { detail: candidateId }),
  );
  dialog.showModal();
}
if (root) {
  const searchRoot = root;
  const form = root.querySelector<HTMLFormElement>("[data-search-form]")!;
  const list = root.querySelector<HTMLElement>("[data-criteria-list]")!;
  const results = root.querySelector<HTMLElement>("[data-results]")!;
  const status = root.querySelector<HTMLElement>(".search-status")!;
  const context = form.elements.namedItem("context") as HTMLSelectElement;
  const openingRow = root.querySelector<HTMLElement>("[data-opening-row]")!;
  const more = root.querySelector<HTMLButtonElement>("[data-more]")!;
  let lastPayload: Record<string, unknown> | null = null;
  let nextCursor: string | null = null;
  list.append(criterionRow());
  root
    .querySelector("[data-add-criterion]")
    ?.addEventListener("click", () => list.append(criterionRow()));
  context.addEventListener(
    "change",
    () => (openingRow.hidden = context.value !== "OPENING"),
  );
  root
    .querySelector("[data-toggle-criteria]")
    ?.addEventListener("click", (event) => {
      const button = event.currentTarget as HTMLButtonElement;
      const expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      root.querySelector<HTMLElement>("[data-criteria-panel]")!.hidden =
        expanded;
    });
  root
    .querySelector("[data-close-detail]")
    ?.addEventListener("click", () =>
      root.querySelector<HTMLDialogElement>("[data-candidate-dialog]")!.close(),
    );
  async function runSearch(payload: Record<string, unknown>, append = false) {
    status.textContent = append
      ? "Loading more authorized profiles…"
      : "Searching authorized profiles…";
    if (!append) results.innerHTML = "<p>Loading results…</p>";
    const response = await fetch(
      `/api/v1/tenants/${searchRoot.dataset.tenantId}/searches`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          "X-Tenant-ID": searchRoot.dataset.tenantId!,
        },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      },
    );
    if (!response.ok) {
      if (!append)
        results.innerHTML =
          "<p>Search could not be completed. Your typed query and criteria remain available.</p>";
      status.textContent = "Search failed safely.";
      more.hidden = true;
      return null;
    }
    const data = (await response.json()) as SearchResponse;
    if (!append) results.innerHTML = "";
    if (!data.items.length && !append)
      results.innerHTML =
        "<p>No authorized candidates matched. Broaden deterministic criteria or choose another active opening.</p>";
    else
      data.items.forEach((item) => results.append(card(item, data.search_id)));
    nextCursor = data.next_cursor;
    more.hidden = nextCursor === null;
    status.textContent = `${data.items.length} result(s) loaded.`;
    results.focus();
    return data;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const entries = readCriteria(list);
    const openingId = (
      form.elements.namedItem("opening_id") as HTMLInputElement
    ).value.trim();
    if (context.value === "OPENING" && !openingId) {
      status.textContent = "Choose an active opening before searching.";
      return;
    }
    const prompt = (
      form.elements.namedItem("prompt") as HTMLTextAreaElement
    ).value.trim();
    const populatedEntries = entries.filter(
      (entry) => String(entry.criterion.value).trim().length > 0,
    );
    if (!populatedEntries.length) {
      status.textContent = "Interpreting the hiring need…";
      const contextPayload =
        context.value === "OPENING"
          ? { type: "OPENING", opening_id: openingId }
          : { type: "AD_HOC" };
      const response = await fetch(
        `/api/v1/tenants/${searchRoot.dataset.tenantId}/searches/interpret`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken(),
            "X-Tenant-ID": searchRoot.dataset.tenantId!,
          },
          credentials: "same-origin",
          body: JSON.stringify({ prompt, context: contextPayload }),
        },
      );
      if (!response.ok) {
        status.textContent =
          "Interpretation is unavailable. Add manual criteria to continue.";
        return;
      }
      const interpretation = (await response.json()) as InterpretationResponse;
      if (interpretation.requires_review) {
        sessionStorage.setItem(REVIEW_KEY, JSON.stringify(interpretation));
        window.dispatchEvent(
          new Event("recruiter-search-intentional-navigation"),
        );
        window.location.assign(
          `/tenants/${searchRoot.dataset.tenantId}/recruiter/search/criteria-review/`,
        );
        return;
      }
      lastPayload = interpretation.criteria;
      await runSearch(lastPayload);
      return;
    }
    lastPayload = {
      context:
        context.value === "OPENING"
          ? {
              type: "OPENING",
              opening_id: openingId,
            }
          : { type: "AD_HOC" },
      groups: populatedEntries.map((v) => v.group),
      criteria: populatedEntries.map((v) => v.criterion),
      limit: 25,
    };
    await runSearch(lastPayload);
  });
  more.addEventListener("click", async () => {
    if (!lastPayload || !nextCursor) return;
    await runSearch({ ...lastPayload, cursor: nextCursor }, true);
  });
  root.querySelectorAll<HTMLButtonElement>("[data-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      root
        .querySelectorAll<HTMLButtonElement>("[data-filter]")
        .forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      root
        .querySelectorAll<HTMLElement>(".candidate-card")
        .forEach(
          (item) =>
            (item.hidden =
              button.dataset.filter === "with-findings" &&
              item.dataset.findings === "0"),
        );
    }),
  );
  const confirmed = sessionStorage.getItem(RESULT_KEY);
  if (confirmed) {
    sessionStorage.removeItem(RESULT_KEY);
    const data = JSON.parse(confirmed) as SearchResponse;
    results.innerHTML = "";
    data.items.forEach((item) => results.append(card(item, data.search_id)));
    nextCursor = data.next_cursor;
    more.hidden = nextCursor === null;
    status.textContent = `${data.items.length} confirmed result(s) loaded.`;
  }
}
