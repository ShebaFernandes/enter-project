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
const root = document.querySelector<HTMLElement>("[data-recruiter-search]");

function cookie(name: string) {
  return (
    document.cookie
      .split(";")
      .map((v) => v.trim())
      .find((v) => v.startsWith(`${name}=`))
      ?.split("=")[1] ?? ""
  );
}
function criterionRow() {
  const id = crypto.randomUUID();
  const row = document.createElement("fieldset");
  row.dataset.criterionId = id;
  row.innerHTML = `<legend>Criterion</legend><label>Purpose <select name="purpose"><option>REQUIREMENT</option><option>PREFERENCE</option><option>EXCLUSION</option></select></label><label>Match <select name="group_operator"><option>ALL</option><option>ANY</option></select></label><label>Field <select name="field"><option value="skill">Skill</option><option value="experience_years">Experience</option><option value="location">Location</option><option value="work_arrangement">Work arrangement</option><option value="availability_date">Availability</option><option value="role_category">Role category</option></select></label><label>Operator <select name="operator"><option>CONTAINS</option><option>EQ</option><option>GTE</option><option>LTE</option></select></label><label>Value <input name="value" required></label><button type="button">Remove</button>`;
  row.querySelector("button")?.addEventListener("click", () => row.remove());
  return row;
}
function readCriteria(container: HTMLElement) {
  return [...container.querySelectorAll<HTMLElement>("fieldset")].map((row) => {
    const value = (name: string) =>
      row.querySelector<HTMLSelectElement | HTMLInputElement>(`[name=${name}]`)!
        .value;
    const group = {
      id: row.dataset.criterionId!,
      purpose: value("purpose"),
      operator: value("group_operator"),
      label: value("field"),
    };
    return {
      group,
      criterion: {
        id: crypto.randomUUID(),
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
          "X-CSRFToken": cookie("__Host-enter_csrf"),
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
      return;
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
    lastPayload = {
      context:
        context.value === "OPENING"
          ? {
              type: "OPENING",
              opening_id: openingId,
            }
          : { type: "AD_HOC" },
      groups: entries.map((v) => v.group),
      criteria: entries.map((v) => v.criterion),
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
}
