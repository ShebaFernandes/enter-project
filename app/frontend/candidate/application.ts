import { clearDraft, loadDraft, saveDraft } from "../shared/persistence";

type Opening = {
  id: string;
  title: string;
  location: Record<string, string>;
  work_mode: string;
  employment_type: string;
};

const root = document.querySelector<HTMLElement>("[data-application-page]");
if (root) {
  const openingId = root.dataset.openingId ?? "";
  const form = root.querySelector<HTMLFormElement>("[data-application-form]")!;
  const status = root.querySelector<HTMLElement>("[data-application-status]")!;
  const errors = root.querySelector<HTMLElement>("[data-form-errors]")!;
  let saved = false;
  let etag = "";
  const csrf = () =>
    document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? "";

  const renderOpening = async () => {
    const response = await fetch(`/api/v1/public/openings/${openingId}`);
    if (!response.ok) {
      status.textContent =
        "This role is unavailable. Your application has not changed.";
      form.hidden = true;
      return;
    }
    const opening = (await response.json()) as Opening;
    root.querySelector<HTMLElement>("[data-opening-title]")!.textContent =
      opening.title;
    root.querySelector<HTMLElement>("[data-role-essentials]")!.innerHTML = `
      <div><dt>Location</dt><dd>${opening.location.display ?? opening.location.city ?? "Not specified"}</dd></div>
      <div><dt>Work arrangement</dt><dd>${opening.work_mode.replaceAll("_", " ")}</dd></div>
      <div><dt>Employment type</dt><dd>${opening.employment_type.replaceAll("_", " ")}</dd></div>`;
  };

  const key = `application-draft:${openingId}`;
  const draft = loadDraft<Record<string, string | boolean>>(key);
  if (draft) {
    for (const [name, value] of Object.entries(draft)) {
      const input = form.elements.namedItem(name);
      if (input instanceof HTMLInputElement && input.type === "checkbox")
        input.checked = Boolean(value);
      else if (
        input instanceof HTMLInputElement ||
        input instanceof HTMLTextAreaElement
      )
        input.value = String(value);
    }
  }
  form.addEventListener("input", () => {
    saved = false;
    const data = new FormData(form);
    saveDraft(key, {
      full_name: String(data.get("full_name") ?? ""),
      email: String(data.get("email") ?? ""),
      motivation: String(data.get("motivation") ?? ""),
      email_updates: data.has("email_updates"),
      whatsapp_updates: data.has("whatsapp_updates"),
      consent: data.has("consent"),
    });
  });
  window.addEventListener("beforeunload", (event) => {
    if (!saved && form.matches(":valid") && new FormData(form).get("full_name"))
      event.preventDefault();
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errors.hidden = true;
    if (!form.reportValidity()) {
      form.querySelector<HTMLElement>(":invalid")?.focus();
      return;
    }
    const resumeId = root.dataset.resumeId;
    const consentId = root.dataset.consentId;
    if (!resumeId || !consentId) {
      status.textContent =
        "Sign in and confirm role-specific consent before applying. Your details are preserved.";
      return;
    }
    status.textContent = "Submitting…";
    const data = new FormData(form);
    const response = await fetch("/api/v1/candidate/applications", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
        "X-CSRFToken": csrf(),
      },
      body: JSON.stringify({
        opening_id: openingId,
        resume_id: resumeId,
        answers: { motivation: String(data.get("motivation") ?? "") },
        consent_record_id: consentId,
        notification_preferences: {
          email: data.has("email_updates"),
          whatsapp: data.has("whatsapp_updates"),
        },
      }),
    });
    if (!response.ok) {
      const problem = (await response.json()) as { title?: string };
      status.textContent =
        response.status === 409
          ? "You already applied to this role."
          : `${problem.title ?? "Application failed"}. Your details are preserved; try again safely.`;
      return;
    }
    etag = response.headers.get("ETag") ?? "";
    void etag;
    saved = true;
    clearDraft(key);
    status.textContent =
      "Application submitted. Your status is Applied; you can now track progress.";
  });
  void renderOpening();
}
