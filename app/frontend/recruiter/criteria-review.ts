import { escapeText } from "./candidate-findings";
import { handoffToken, workflowTransport } from "../shared/workflow-handoff";

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
  etag: string;
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
  const transport = workflowTransport(tenantId);
  const token = handoffToken();
  let ready = false;
  let state: ReviewState = {
    etag: "",
    original_prompt:
      "Structured criteria restored securely; the original prompt is not retained here.",
    criteria: {
      context: { type: "AD_HOC" },
      groups: [],
      criteria: [],
      limit: 25,
    },
    estimated_count: Number(count.textContent ?? 0),
  };
  let estimateTimer = 0;
  let estimateWork: Promise<void> = Promise.resolve();

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
      if (!token || !ready) throw new Error("Review unavailable");
      const updated = await transport.revise<ReviewState>(
        token,
        state.etag,
        state.criteria,
      );
      state = { ...state, ...updated };
      count.textContent = String(state.estimated_count);
      status.textContent = "Estimated impact updated.";
    } catch {
      status.textContent =
        "Estimated impact is unavailable. Your criteria remain editable.";
    }
  }

  function scheduleEstimate() {
    window.clearTimeout(estimateTimer);
    estimateTimer = window.setTimeout(() => {
      estimateWork = estimateWork.then(refreshEstimate);
    }, 250);
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
      if (!ready || !token) return;
      window.clearTimeout(estimateTimer);
      await estimateWork;
      syncFromDom();
      if (!state.criteria.criteria.length) {
        status.textContent =
          "Add at least one criterion before running the search.";
        return;
      }
      status.textContent = "Running the confirmed criteria…";
      try {
        state = {
          ...state,
          ...(await transport.revise<ReviewState>(
            token,
            state.etag,
            state.criteria,
          )),
        };
        const response = await transport.client(
          `/api/v1/tenants/${tenantId}/searches`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrfToken(),
              "X-Tenant-ID": tenantId,
            },
            credentials: "same-origin",
            body: JSON.stringify(state.criteria),
          },
        );
        if (!response.ok) {
          status.textContent =
            "Search failed safely. Your confirmed criteria remain available.";
          return;
        }
        const result = (await response.json()) as { search_id: string };
        const resultsToken = await transport.create("search-results", {
          search_id: result.search_id,
          criteria_token: token,
        });
        transport.navigate("search-results", resultsToken);
      } catch {
        status.textContent =
          "Review expired, changed or became unavailable. Return to search to start again.";
      }
    });
  const returnLink = document.createElement("a");
  returnLink.href = `/tenants/${tenantId}/recruiter/search/`;
  returnLink.textContent = "Return to search";
  status.after(returnLink);
  if (token) {
    status.textContent = "Restoring authorized criteria…";
    void transport
      .restore<ReviewState>("criteria-review", token)
      .then((restored) => {
        state = { ...state, ...restored };
        ready = true;
        render();
        status.textContent = "Criteria restored. Review before confirming.";
      })
      .catch(() => {
        status.textContent =
          "Review expired, was revoked or is unavailable for this session. Return to search.";
      });
  } else {
    status.textContent = "No active review. Return to search.";
  }
}
