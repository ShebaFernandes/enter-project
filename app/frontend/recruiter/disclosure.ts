type DisclosurePreview = {
  preview_id: string;
  preview_hash: string;
  destination: { type: string; label: string };
  purpose: string;
  permitted_fields: string[];
  excluded_fields: string[];
  expires_at: string;
  state: string;
  result_category?: string | null;
};

function csrfToken(root: HTMLElement): string {
  return (
    root.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")?.value ??
    ""
  );
}

export function configureDisclosure(
  root: HTMLElement,
  context: { type: "APPLICATION" | "CANDIDATE_WORK"; id: string },
): void {
  const form = root.querySelector<HTMLFormElement>("[data-disclosure-form]");
  const previewRegion = root.querySelector<HTMLElement>(
    "[data-disclosure-preview]",
  );
  const statusRegion = root.querySelector<HTMLElement>(
    "[data-disclosure-status]",
  );
  const confirm = root.querySelector<HTMLButtonElement>(
    "[data-confirm-disclosure]",
  );
  if (!form || !previewRegion || !statusRegion || !confirm) return;
  let preview: DisclosurePreview | null = null;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const fields = [
      ...form.querySelectorAll<HTMLInputElement>("[name=fields]:checked"),
    ].map((input) => input.value);
    statusRegion.textContent = "Checking current consent and field access…";
    const response = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/candidates/${root.dataset.candidateId}/disclosures/preview`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(root),
          "X-Tenant-ID": root.dataset.tenantId!,
          "Idempotency-Key": crypto.randomUUID(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          context_type: context.type,
          context_id: context.id,
          purpose: data.get("purpose"),
          destination: {
            type: data.get("destination_type"),
            identifier: data.get("destination_identifier"),
            label: data.get("destination_label"),
          },
          requested_fields: fields,
        }),
      },
    );
    if (!response.ok) {
      preview = null;
      previewRegion.hidden = true;
      confirm.hidden = true;
      statusRegion.textContent =
        "Disclosure is unavailable. No candidate information was shared.";
      return;
    }
    preview = (await response.json()) as DisclosurePreview;
    previewRegion.hidden = false;
    previewRegion.textContent = `Destination: ${preview.destination.label}. Purpose: ${preview.purpose}. Fields to disclose: ${preview.permitted_fields.join(", ")}. Excluded: ${preview.excluded_fields.join(", ") || "none"}.`;
    confirm.hidden = false;
    statusRegion.textContent =
      "Review the minimum-data preview before confirming.";
  });
  confirm.addEventListener("click", async () => {
    if (!preview) return;
    confirm.disabled = true;
    statusRegion.textContent = "Disclosure pending…";
    const response = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/candidates/${root.dataset.candidateId}/disclosures`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(root),
          "X-Tenant-ID": root.dataset.tenantId!,
          "Idempotency-Key": crypto.randomUUID(),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          preview_id: preview.preview_id,
          preview_hash: preview.preview_hash,
          confirm: true,
        }),
      },
    );
    confirm.disabled = false;
    if (!response.ok) {
      statusRegion.textContent =
        "Consent or access changed. Nothing was shared; create a new preview.";
      confirm.hidden = true;
      return;
    }
    const result = (await response.json()) as DisclosurePreview;
    statusRegion.textContent =
      result.state === "PENDING"
        ? "Disclosure accepted and pending delivery."
        : `Disclosure result: ${result.state.toLowerCase()}.`;
    confirm.hidden = true;
  });
}
