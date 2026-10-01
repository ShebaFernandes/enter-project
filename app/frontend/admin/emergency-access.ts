type EmergencyAccess = {
  id: string;
  reason_code: string;
  field_scope: string[];
  operation_scope: string[];
  object_count: number;
  status: string;
  expires_at: string | null;
};

export {};

const emergencyRoot = document.querySelector<HTMLElement>("[data-governance]");
const emergencyData = document.querySelector<HTMLScriptElement>(
  "#emergency-access-data",
);
if (emergencyRoot && emergencyData) {
  const tenantId = emergencyRoot.dataset.tenantId!;
  const list = emergencyRoot.querySelector<HTMLElement>(
    "[data-emergency-list]",
  )!;
  const values = JSON.parse(
    emergencyData.textContent ?? "[]",
  ) as EmergencyAccess[];
  const csrf =
    emergencyRoot.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? "";
  list.replaceChildren(
    ...values.map((value) => {
      const row = document.createElement("li");
      const summary = document.createElement("p");
      summary.textContent = `${value.reason_code} — ${value.operation_scope.join(", ")} — fields ${value.field_scope.join(", ")} — ${value.object_count} scoped object(s) — expires ${value.expires_at ?? "unavailable"}`;
      const revoke = document.createElement("button");
      revoke.type = "button";
      revoke.textContent = "Revoke emergency access";
      revoke.addEventListener("click", async () => {
        const response = await fetch(
          `/api/v1/tenants/${tenantId}/emergency-access-grants/${value.id}/revoke`,
          {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "X-Tenant-ID": tenantId,
              "X-CSRFToken": csrf,
              "Idempotency-Key": crypto.randomUUID(),
            },
          },
        );
        emergencyRoot.querySelector<HTMLElement>(
          "[data-organization-status]",
        )!.textContent = response.ok
          ? "Emergency access revoked."
          : "Emergency access was not revoked.";
        if (response.ok) row.remove();
      });
      row.append(summary, revoke);
      return row;
    }),
  );
  if (!values.length)
    list.append(
      Object.assign(document.createElement("li"), {
        textContent: "No active emergency access.",
      }),
    );
}
