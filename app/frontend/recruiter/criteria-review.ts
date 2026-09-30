import { escapeText } from "./candidate-findings";

type Group = {
  id: string;
  purpose: "REQUIREMENT" | "PREFERENCE" | "EXCLUSION";
  operator: "ANY" | "ALL";
  label?: string | null;
};
type Criterion = {
  id: string;
  group_id: string;
  field: string;
  operator: string;
  value: unknown;
};
type ReviewState = {
  workflow_id?: string;
  original_prompt: string;
  criteria: {
    context: Record<string, string>;
    groups: Group[];
    criteria: Criterion[];
    limit: number;
  };
  estimated_count: number;
  group_impacts?: {
    group_id: string;
    operator: "ANY" | "ALL";
    estimated_count: number;
    alternate_operator: "ANY" | "ALL";
    alternate_estimated_count: number;
  }[];
  ambiguities?: string[];
};

const reviewRoot = document.querySelector<HTMLElement>(
  "[data-criteria-review]",
);
const REVIEW_KEY = "enter.criteria-review.v1";
const RESULT_KEY = "enter.confirmed-search.v1";

function csrfToken() {
  return (
    document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? ""
  );
}

if (reviewRoot) {
  const groupsRoot = reviewRoot.querySelector<HTMLElement>("[data-groups]")!;
  const status = reviewRoot.querySelector<HTMLElement>("[data-review-status]")!;
  const count = reviewRoot.querySelector<HTMLElement>(
    "[data-estimated-count]",
  )!;
  const promptNode = reviewRoot.querySelector<HTMLElement>(
    "[data-original-prompt]",
  )!;
  const tenantId = reviewRoot.dataset.tenantId ?? "";
  const stored = sessionStorage.getItem(REVIEW_KEY);
  let state: ReviewState = stored
    ? (JSON.parse(stored) as ReviewState)
    : {
        original_prompt: promptNode.textContent?.trim() ?? "",
        criteria: {
          context: { type: "AD_HOC" },
          groups: [],
          criteria: [],
          limit: 25,
        },
        estimated_count: Number(count.textContent ?? 0),
      };
  let estimateTimer = 0;

  function groupOptions(selected: string) {
    return state.criteria.groups
      .map(
        (group) =>
          `<option value="${group.id}" ${group.id === selected ? "selected" : ""}>${escapeText(group.label || group.purpose)} (${group.id})</option>`,
      )
      .join("");
  }

  function render() {
    promptNode.textContent = state.original_prompt;
    count.textContent = String(state.estimated_count);
    groupsRoot.innerHTML = "";
    for (const group of state.criteria.groups) {
      const impact = state.group_impacts?.find(
        (item) => item.group_id === group.id,
      );
      const section = document.createElement("fieldset");
      section.dataset.groupId = group.id;
      section.className = "criteria-group";
      section.innerHTML = `<legend>Criteria group</legend>
        <p class="stable-id">Stable group ID: ${group.id}</p>
        <label>Purpose <select name="purpose"><option>REQUIREMENT</option><option>PREFERENCE</option><option>EXCLUSION</option></select></label>
        <label>Match within group <select name="operator"><option>ALL</option><option>ANY</option></select></label>
        <p class="group-help">ANY includes a candidate when one criterion matches. ALL requires every criterion to match.</p>
        <p data-group-impact>${
          impact
            ? `Estimated impact: ${impact.operator} ${impact.estimated_count}; ${impact.alternate_operator} ${impact.alternate_estimated_count} candidates.`
            : "Estimated impact updates after valid criteria are entered."
        }</p>
        <div data-group-criteria></div>
        <button type="button" data-add-criterion>Add criterion</button>
        <button type="button" data-remove-group>Remove group</button>`;
      section.querySelector<HTMLSelectElement>("[name=purpose]")!.value =
        group.purpose;
      section.querySelector<HTMLSelectElement>("[name=operator]")!.value =
        group.operator;
      const criteriaRoot = section.querySelector<HTMLElement>(
        "[data-group-criteria]",
      )!;
      for (const criterion of state.criteria.criteria.filter(
        (item) => item.group_id === group.id,
      )) {
        const row = document.createElement("fieldset");
        row.dataset.criterionId = criterion.id;
        row.className = "criterion-row";
        row.innerHTML = `<legend>Criterion</legend>
          <p class="stable-id">Stable criterion ID: ${criterion.id}</p>
          <label>Group membership <select name="group_id">${groupOptions(criterion.group_id)}</select></label>
          <label>Field <select name="field"><option value="skill">Skill</option><option value="experience_years">Experience</option><option value="location">Location</option><option value="work_arrangement">Work arrangement</option><option value="availability_date">Availability</option><option value="role_category">Role category</option></select></label>
          <label>Operator <select name="criterion_operator"><option>CONTAINS</option><option>EQ</option><option>NE</option><option>GTE</option><option>LTE</option><option>IN</option><option>NOT_IN</option><option>EXISTS</option></select></label>
          <label>Value <input name="value" required></label>
          <button type="button" data-remove-criterion>Remove criterion</button>`;
        row.querySelector<HTMLSelectElement>("[name=field]")!.value =
          criterion.field;
        row.querySelector<HTMLSelectElement>(
          "[name=criterion_operator]",
        )!.value = criterion.operator;
        row.querySelector<HTMLInputElement>("[name=value]")!.value = String(
          criterion.value ?? "",
        );
        criteriaRoot.append(row);
      }
      groupsRoot.append(section);
    }
  }

  function syncFromDom() {
    const groups: Group[] = [];
    const criteria: Criterion[] = [];
    groupsRoot
      .querySelectorAll<HTMLElement>("[data-group-id]")
      .forEach((node) => {
        const id = node.dataset.groupId!;
        groups.push({
          id,
          purpose: node.querySelector<HTMLSelectElement>("[name=purpose]")!
            .value as Group["purpose"],
          operator: node.querySelector<HTMLSelectElement>("[name=operator]")!
            .value as Group["operator"],
          label: "Recruiter-defined group",
        });
        node
          .querySelectorAll<HTMLElement>("[data-criterion-id]")
          .forEach((row) => {
            criteria.push({
              id: row.dataset.criterionId!,
              group_id:
                row.querySelector<HTMLSelectElement>("[name=group_id]")!.value,
              field:
                row.querySelector<HTMLSelectElement>("[name=field]")!.value,
              operator: row.querySelector<HTMLSelectElement>(
                "[name=criterion_operator]",
              )!.value,
              value: row.querySelector<HTMLInputElement>("[name=value]")!.value,
            });
          });
      });
    state.criteria.groups = groups;
    state.criteria.criteria = criteria;
  }

  async function refreshEstimate() {
    syncFromDom();
    if (
      !tenantId ||
      !state.criteria.groups.length ||
      !state.criteria.criteria.length
    )
      return;
    status.textContent = "Updating estimated impact…";
    try {
      const response = await fetch(
        `/api/v1/tenants/${tenantId}/searches/interpret`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken(),
            "X-Tenant-ID": tenantId,
          },
          credentials: "same-origin",
          body: JSON.stringify({
            prompt: state.original_prompt,
            context: state.criteria.context,
            criteria: state.criteria,
            workflow_id: state.workflow_id,
          }),
        },
      );
      if (!response.ok) throw new Error("invalid review");
      const updated = (await response.json()) as ReviewState;
      state = updated;
      count.textContent = String(state.estimated_count);
      sessionStorage.setItem(REVIEW_KEY, JSON.stringify(state));
      status.textContent = "Estimated impact updated.";
    } catch {
      status.textContent =
        "Estimated impact is unavailable. Your criteria remain editable.";
    }
  }

  function scheduleEstimate() {
    window.clearTimeout(estimateTimer);
    estimateTimer = window.setTimeout(refreshEstimate, 250);
  }

  reviewRoot
    .querySelector("[data-add-group]")
    ?.addEventListener("click", () => {
      state.criteria.groups.push({
        id: crypto.randomUUID(),
        purpose: "REQUIREMENT",
        operator: "ALL",
        label: "Recruiter-defined group",
      });
      render();
    });
  groupsRoot.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    const groupNode = target.closest<HTMLElement>("[data-group-id]");
    if (!groupNode) return;
    if (target.matches("[data-add-criterion]")) {
      syncFromDom();
      state.criteria.criteria.push({
        id: crypto.randomUUID(),
        group_id: groupNode.dataset.groupId!,
        field: "skill",
        operator: "CONTAINS",
        value: "",
      });
      render();
    } else if (target.matches("[data-remove-criterion]")) {
      target.closest("[data-criterion-id]")?.remove();
      scheduleEstimate();
    } else if (target.matches("[data-remove-group]")) {
      groupNode.remove();
      scheduleEstimate();
    }
  });
  groupsRoot.addEventListener("change", (event) => {
    if ((event.target as HTMLSelectElement).name === "group_id") {
      syncFromDom();
      render();
    }
    scheduleEstimate();
  });
  groupsRoot.addEventListener("input", scheduleEstimate);
  reviewRoot
    .querySelector<HTMLFormElement>("[data-review-form]")!
    .addEventListener("submit", async (event) => {
      event.preventDefault();
      syncFromDom();
      if (!state.criteria.criteria.length) {
        status.textContent =
          "Add at least one criterion before running the search.";
        return;
      }
      status.textContent = "Running the confirmed criteria…";
      const response = await fetch(`/api/v1/tenants/${tenantId}/searches`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          "X-Tenant-ID": tenantId,
        },
        credentials: "same-origin",
        body: JSON.stringify(state.criteria),
      });
      if (!response.ok) {
        status.textContent =
          "Search failed safely. Your confirmed criteria remain available.";
        return;
      }
      sessionStorage.setItem(RESULT_KEY, JSON.stringify(await response.json()));
      sessionStorage.removeItem(REVIEW_KEY);
      window.location.assign(`/tenants/${tenantId}/recruiter/search/`);
    });
  render();
}
