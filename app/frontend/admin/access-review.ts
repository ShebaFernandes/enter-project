type Review = {
  id: string;
  review_type: string;
  state: string;
  due_at: string;
  remediation_state: string;
  etag: string;
  items: {
    id: string;
    assignment_type: string;
    evidence: Record<string, unknown>;
    decision: string;
  }[];
};

export {};

const governance = document.querySelector<HTMLElement>("[data-governance]");
if (governance) {
  const tenantId = governance.dataset.tenantId!;
  const csrf =
    governance.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? "";
  const headers = () => ({
    "X-Tenant-ID": tenantId,
    "X-CSRFToken": csrf,
  });
  const tabs = [
    ...governance.querySelectorAll<HTMLButtonElement>("[data-governance-tab]"),
  ];
  const panels = [
    ...governance.querySelectorAll<HTMLElement>("[data-governance-panel]"),
  ];
  const auditList = governance.querySelector<HTMLElement>("[data-audit-list]")!;
  const reviewList =
    governance.querySelector<HTMLElement>("[data-review-list]")!;
  const reviewEmpty = governance.querySelector<HTMLElement>(
    "[data-review-empty]",
  )!;

  const show = (name: string) => {
    tabs.forEach((tab) => {
      const selected = tab.dataset.governanceTab === name;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    panels.forEach(
      (panel) => (panel.hidden = panel.dataset.governancePanel !== name),
    );
  };

  const loadAudit = async () => {
    const response = await fetch(`/api/v1/tenants/${tenantId}/audit-events`, {
      credentials: "same-origin",
      headers: headers(),
    });
    if (!response.ok) return;
    const values = (await response.json()) as {
      action: string;
      outcome: string;
      occurred_at: string;
    }[];
    auditList.replaceChildren(
      ...values.map((value) => {
        const row = document.createElement("li");
        row.textContent = `${value.action} — ${value.outcome} — ${value.occurred_at}`;
        return row;
      }),
    );
  };

  const loadReviews = async () => {
    const response = await fetch(`/api/v1/tenants/${tenantId}/access-reviews`, {
      credentials: "same-origin",
      headers: headers(),
    });
    if (!response.ok) return;
    const values = (await response.json()) as Review[];
    reviewEmpty.hidden = values.length > 0;
    reviewList.replaceChildren(
      ...values.map((value) => {
        const row = document.createElement("li");
        const summary = document.createElement("p");
        summary.textContent = `${value.review_type} — ${value.state} — remediation ${value.remediation_state} — due ${value.due_at}`;
        row.append(summary);
        if (value.state !== "COMPLETED") {
          value.items
            .filter((item) => item.decision === "PENDING")
            .forEach((item) => {
              const evidence = document.createElement("p");
              evidence.textContent = `${item.assignment_type}: ${JSON.stringify(item.evidence)}`;
              const revoke = document.createElement("button");
              revoke.type = "button";
              revoke.textContent = `Revoke ${item.assignment_type.toLowerCase()} access`;
              revoke.addEventListener("click", async () => {
                const response = await fetch(
                  `/api/v1/tenants/${tenantId}/access-reviews/${value.id}/complete`,
                  {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                      ...headers(),
                      "Content-Type": "application/json",
                      "Idempotency-Key": crypto.randomUUID(),
                      "If-Match": value.etag,
                    },
                    body: JSON.stringify({
                      decisions: [
                        {
                          item_id: item.id,
                          decision: "REVOKE",
                          finding: "Access no longer required",
                        },
                      ],
                    }),
                  },
                );
                governance.querySelector<HTMLElement>(
                  "[data-organization-status]",
                )!.textContent = response.ok
                  ? "Access revoked and review evidence recorded."
                  : response.status === 409
                    ? "Review changed; reload before deciding."
                    : "Access was not revoked.";
                if (response.ok) await loadReviews();
              });
              row.append(evidence, revoke);
            });
        }
        return row;
      }),
    );
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      show(tab.dataset.governanceTab!);
      if (tab.dataset.governanceTab === "audit") void loadAudit();
      if (tab.dataset.governanceTab === "review") void loadReviews();
    });
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const target = tabs[(index + offset + tabs.length) % tabs.length];
      target.focus();
      target.click();
    });
  });

  governance
    .querySelector<HTMLFormElement>("[data-access-review-form]")
    ?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget as HTMLFormElement;
      const data = new FormData(form);
      const response = await fetch(
        `/api/v1/tenants/${tenantId}/access-reviews`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            ...headers(),
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({
            review_type: data.get("review_type"),
            due_at: data.get("due_at"),
          }),
        },
      );
      governance.querySelector<HTMLElement>(
        "[data-organization-status]",
      )!.textContent = response.ok
        ? "Access review started."
        : "Access review was not started.";
      if (response.ok) await loadReviews();
    });
}
