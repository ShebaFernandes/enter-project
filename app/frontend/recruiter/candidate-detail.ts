import {
  showConflict,
  type ConflictPayload,
} from "../shared/conflict-resolution";
import { warnOnUnsaved } from "../shared/persistence";
import { configureDisclosure } from "./disclosure";

type CandidateDetail = {
  candidate_id: string;
  permitted_fields: Record<string, unknown>;
  evidence: unknown[];
  findings: { message: string }[];
  unknowns: string[];
  candidate_work: {
    id: string;
    version: number;
    internal_status: string;
    shortlisted: boolean;
  };
  application_context?: {
    id: string;
    version: number;
    etag: string;
    internal_status: string;
    candidate_status: string;
  } | null;
};

const root = document.querySelector<HTMLElement>("[data-candidate-management]");

function csrfToken(): string {
  return (
    root?.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? ""
  );
}

function headers(idempotent = false): Record<string, string> {
  const values: Record<string, string> = {
    "Content-Type": "application/json",
    "X-CSRFToken": csrfToken(),
    "X-Tenant-ID": root!.dataset.tenantId!,
  };
  if (idempotent) values["Idempotency-Key"] = crypto.randomUUID();
  return values;
}

function markDirty(form: HTMLFormElement): void {
  form.dataset.dirty = "true";
}

if (root) {
  const searchId = new URLSearchParams(location.search).get("search_id");
  const status = root.querySelector<HTMLElement>("[data-page-status]")!;
  const summary = root.querySelector<HTMLElement>("[data-candidate-summary]")!;
  const noteForm = root.querySelector<HTMLFormElement>("[data-note-form]")!;
  const workForm = root.querySelector<HTMLFormElement>("[data-work-form]")!;
  const notes = root.querySelector<HTMLElement>("[data-notes]")!;
  let detail: CandidateDetail | null = null;
  let workEtag = "";
  let applicationEtag = "";

  const loadNotes = async () => {
    if (!detail) return;
    const response = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/candidate-work/${detail.candidate_work.id}/notes`,
      { headers: { "X-Tenant-ID": root.dataset.tenantId! } },
    );
    if (!response.ok) return;
    const values = (await response.json()) as {
      body: string;
      created_at: string;
    }[];
    notes.replaceChildren(
      ...values.map((note) => {
        const item = document.createElement("li");
        item.textContent = `${note.body} — ${new Date(note.created_at).toLocaleString()}`;
        return item;
      }),
    );
  };

  const load = async () => {
    if (!searchId) {
      status.textContent =
        "Return to search and open this candidate from an authorized result.";
      return;
    }
    status.textContent = "Loading current authorized candidate context…";
    const response = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/candidates/${root.dataset.candidateId}?search_id=${searchId}`,
      { headers: { "X-Tenant-ID": root.dataset.tenantId! } },
    );
    if (!response.ok) {
      status.textContent = "Candidate details are no longer available.";
      return;
    }
    detail = (await response.json()) as CandidateDetail;
    const workResponse = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/candidate-work/${detail.candidate_work.id}`,
      { headers: { "X-Tenant-ID": root.dataset.tenantId! } },
    );
    workEtag = workResponse.headers.get("ETag") ?? "";
    const work = (await workResponse.json()) as Record<string, unknown>;
    summary.textContent = `${String(detail.permitted_fields.name ?? "Candidate")}. ${String(detail.permitted_fields.current_role ?? "Role not provided")}. ${detail.evidence.length} evidence item(s); ${detail.unknowns.length} unknown field(s).`;
    (
      workForm.elements.namedItem("internal_status") as HTMLSelectElement
    ).value = String(work.internal_status);
    (workForm.elements.namedItem("shortlisted") as HTMLInputElement).checked =
      Boolean(work.shortlisted);
    root.dataset.etag = workEtag;
    if (detail.application_context) {
      applicationEtag = detail.application_context.etag;
    }
    await loadNotes();
    configureDisclosure(root, {
      type: "CANDIDATE_WORK",
      id: detail.candidate_work.id,
    });
    status.textContent = "Candidate context loaded.";
  };

  noteForm.addEventListener("input", () => markDirty(noteForm));
  noteForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!detail) return;
    status.textContent = "Saving private note…";
    const body = (noteForm.elements.namedItem("body") as HTMLTextAreaElement)
      .value;
    const response = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/candidate-work/${detail.candidate_work.id}/notes`,
      {
        method: "POST",
        headers: headers(true),
        body: JSON.stringify({ body }),
      },
    );
    if (!response.ok) {
      status.textContent =
        "Private note was not saved. Your text remains in the form.";
      return;
    }
    noteForm.reset();
    noteForm.dataset.dirty = "false";
    await loadNotes();
    status.textContent =
      "Private note saved. It is not visible to the candidate.";
  });

  workForm.addEventListener("input", () => markDirty(workForm));
  workForm.addEventListener("change", () => markDirty(workForm));
  workForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!detail) return;
    const internalStatus = (
      workForm.elements.namedItem("internal_status") as HTMLSelectElement
    ).value;
    const reason = (
      workForm.elements.namedItem("structured_reason") as HTMLInputElement
    ).value.trim();
    const response = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/candidate-work/${detail.candidate_work.id}`,
      {
        method: "PATCH",
        headers: { ...headers(true), "If-Match": workEtag },
        body: JSON.stringify({
          internal_status: internalStatus,
          shortlisted: (
            workForm.elements.namedItem("shortlisted") as HTMLInputElement
          ).checked,
          structured_reasons: reason ? [reason] : [],
        }),
      },
    );
    if (response.status === 409) {
      showConflict(root, (await response.json()) as ConflictPayload);
      status.textContent =
        "A stale change was rejected; nothing was overwritten.";
      return;
    }
    if (!response.ok) {
      status.textContent =
        "Status was not changed. Add a reason when selecting Not relevant.";
      return;
    }
    workEtag = response.headers.get("ETag") ?? workEtag;
    root.dataset.etag = workEtag;
    workForm.dataset.dirty = "false";
    status.textContent =
      "Internal status and shortlist state saved in this context.";
  });

  const publicationForm = root.querySelector<HTMLFormElement>(
    "[data-publication-form]",
  )!;
  publicationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!detail?.application_context) {
      status.textContent =
        "No linked application exists in this opening context.";
      return;
    }
    const internalStatus = (
      publicationForm.elements.namedItem(
        "publication_internal_status",
      ) as HTMLSelectElement
    ).value;
    const response = await fetch(
      `/api/v1/tenants/${root.dataset.tenantId}/applications/${detail.application_context.id}/status-preview`,
      {
        method: "POST",
        headers: { ...headers(), "If-Match": applicationEtag },
        body: JSON.stringify({ internal_status: internalStatus }),
      },
    );
    const region = root.querySelector<HTMLElement>("[data-status-preview]")!;
    if (!response.ok) {
      status.textContent =
        "Status preview is unavailable; no candidate-facing change occurred.";
      return;
    }
    const preview = (await response.json()) as {
      preview_id: string;
      suggested_candidate_status: string | null;
    };
    applicationEtag = response.headers.get("ETag") ?? applicationEtag;
    region.hidden = false;
    region.textContent = preview.suggested_candidate_status
      ? `Suggested candidate-facing status: ${preview.suggested_candidate_status}. This is not published.`
      : "This internal status has no candidate-facing suggestion. Choose a valid candidate-facing status explicitly before confirmation.";
    publicationForm.dataset.previewId = preview.preview_id;
    root.querySelector<HTMLButtonElement>("[data-publish-status]")!.hidden =
      false;
  });
  root
    .querySelector("[data-publish-status]")
    ?.addEventListener("click", async () => {
      if (!detail?.application_context || !publicationForm.dataset.previewId)
        return;
      const selected = (
        publicationForm.elements.namedItem(
          "candidate_status",
        ) as HTMLSelectElement
      ).value;
      const response = await fetch(
        `/api/v1/tenants/${root.dataset.tenantId}/applications/${detail.application_context.id}/status-publish`,
        {
          method: "POST",
          headers: { ...headers(true), "If-Match": applicationEtag },
          body: JSON.stringify({
            preview_id: publicationForm.dataset.previewId,
            candidate_status: selected,
            confirm: true,
            notify_channels: [],
          }),
        },
      );
      status.textContent = response.ok
        ? "Candidate-facing status published after confirmation."
        : "Candidate-facing status was not published.";
    });

  warnOnUnsaved([noteForm, workForm]);
  void load();
}
