type EmploymentRecord = {
  id?: string;
  company: string;
  role_title: string | null;
  start_date: string | null;
  end_date: string | null;
  start_date_state: "CONFIRMED" | "SUGGESTED" | "AMBIGUOUS" | "MISSING";
  end_date_state: "CONFIRMED" | "SUGGESTED" | "AMBIGUOUS" | "MISSING";
  is_current: boolean;
  employment_type: string;
  employment_type_state: "CONFIRMED" | "SUGGESTED" | "AMBIGUOUS" | "MISSING";
  provenance: "CANDIDATE_REPORTED" | "RESUME_EXTRACTED";
  source_spans: object[];
};

const root = document.querySelector<HTMLElement>("[data-candidate-profile]");

function cookie(name: string): string {
  return (
    document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(`${name}=`))
      ?.split("=")[1] ?? ""
  );
}

function employmentRow(record: Partial<EmploymentRecord> = {}): HTMLElement {
  const wrapper = document.createElement("fieldset");
  wrapper.dataset.employmentId = record.id ?? "";
  wrapper.innerHTML = `<legend>Employment record</legend>
    <label>Company <input name="company" required maxlength="300"></label>
    <label>Role title <input name="role_title" maxlength="300"></label>
    <label>Start date <input name="start_date" type="date"></label>
    <label>Start-date confidence <select name="start_date_state"><option>CONFIRMED</option><option>SUGGESTED</option><option>AMBIGUOUS</option><option>MISSING</option></select></label>
    <label>End date <input name="end_date" type="date"></label>
    <label>End-date confidence <select name="end_date_state"><option>CONFIRMED</option><option>SUGGESTED</option><option>AMBIGUOUS</option><option>MISSING</option></select></label>
    <label><input name="is_current" type="checkbox"> This is my current role</label>
    <label>Employment type <select name="employment_type"><option>PERMANENT</option><option>INTERNSHIP</option><option>APPRENTICESHIP</option><option>FIXED_TERM_CONTRACT</option><option>CONSULTING</option><option>SEASONAL</option><option>OTHER_TEMPORARY</option><option>OTHER</option><option>UNKNOWN</option></select></label>
    <button type="button" data-remove-employment>Remove record</button>`;
  for (const [key, value] of Object.entries(record)) {
    const control = wrapper.querySelector<HTMLInputElement | HTMLSelectElement>(
      `[name="${key}"]`,
    );
    if (!control || value == null) continue;
    if (control instanceof HTMLInputElement && control.type === "checkbox")
      control.checked = Boolean(value);
    else if (typeof value === "string") control.value = value;
  }
  wrapper
    .querySelector("[data-remove-employment]")
    ?.addEventListener("click", () => wrapper.remove());
  return wrapper;
}

function readEmployment(container: HTMLElement): EmploymentRecord[] {
  return [...container.querySelectorAll<HTMLElement>("fieldset")].map((row) => {
    const value = (name: string) =>
      row.querySelector<HTMLInputElement | HTMLSelectElement>(
        `[name="${name}"]`,
      )?.value ?? "";
    return {
      ...(row.dataset.employmentId ? { id: row.dataset.employmentId } : {}),
      company: value("company"),
      role_title: value("role_title") || null,
      start_date: value("start_date") || null,
      end_date: value("end_date") || null,
      start_date_state: value(
        "start_date_state",
      ) as EmploymentRecord["start_date_state"],
      end_date_state: value(
        "end_date_state",
      ) as EmploymentRecord["end_date_state"],
      is_current:
        row.querySelector<HTMLInputElement>("[name=is_current]")?.checked ??
        false,
      employment_type: value("employment_type"),
      employment_type_state: "CONFIRMED",
      provenance: "CANDIDATE_REPORTED",
      source_spans: [],
    };
  });
}

if (root) {
  const form = root.querySelector<HTMLFormElement>("form")!;
  const status = root.querySelector<HTMLElement>(".status")!;
  const errors = root.querySelector<HTMLElement>(".error-summary")!;
  const list = root.querySelector<HTMLElement>("[data-employment-list]")!;
  const completion = root.querySelector<HTMLElement>(
    "[data-completion-message]",
  )!;
  const etag = form.elements.namedItem("etag") as HTMLInputElement;
  const updateCompletion = () => {
    const missing: string[] = [];
    if (
      !(form.elements.namedItem("full_name") as HTMLInputElement).value.trim()
    )
      missing.push("full name");
    if (!(form.elements.namedItem("location") as HTMLInputElement).value.trim())
      missing.push("location");
    if (!(form.elements.namedItem("skills") as HTMLInputElement).value.trim())
      missing.push("skills");
    if (!list.children.length) missing.push("employment history review");
    completion.textContent = missing.length
      ? `Still to review: ${missing.join(", ")}. A clean reviewed resume and active consent are also required before publication.`
      : "Core profile facts are complete. A clean reviewed resume and active consent are also required before publication.";
  };
  root.querySelector("[data-add-employment]")?.addEventListener("click", () => {
    list.append(employmentRow());
    updateCompletion();
  });
  form.addEventListener("input", updateCompletion);
  const narrative = form.elements.namedItem(
    "meaningful_work",
  ) as HTMLTextAreaElement;
  const count = root.querySelector<HTMLOutputElement>("#meaningful-count")!;
  narrative.addEventListener("input", () => {
    count.value = `${narrative.value.length} / 300`;
  });

  const load = async () => {
    const response = await fetch("/api/v1/candidate/profile", {
      credentials: "same-origin",
    });
    if (!response.ok) {
      completion.textContent =
        "Sign in as a verified candidate to load profile requirements.";
      return;
    }
    const data = await response.json();
    etag.value = response.headers.get("ETag") ?? "";
    for (const name of [
      "full_name",
      "experience_years",
      "meaningful_work",
    ] as const) {
      const control = form.elements.namedItem(name) as
        | HTMLInputElement
        | HTMLTextAreaElement;
      control.value = String(data[name] ?? "");
    }
    (form.elements.namedItem("location") as HTMLInputElement).value = String(
      data.location?.display ?? data.location?.city ?? "",
    );
    (form.elements.namedItem("skills") as HTMLInputElement).value =
      data.skills.join(", ");
    data.employment_history.forEach((record: EmploymentRecord) =>
      list.append(employmentRow(record)),
    );
    updateCompletion();
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    errors.hidden = true;
    status.textContent = "Saving…";
    const payload = {
      full_name: (form.elements.namedItem("full_name") as HTMLInputElement)
        .value,
      location: {
        display: (form.elements.namedItem("location") as HTMLInputElement)
          .value,
      },
      experience_years: (
        form.elements.namedItem("experience_years") as HTMLInputElement
      ).value,
      skills: (form.elements.namedItem("skills") as HTMLInputElement).value
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
      meaningful_work: narrative.value,
      role_categories: (
        form.elements.namedItem("role_categories") as HTMLInputElement
      ).value
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
      preferred_locations: (
        form.elements.namedItem("preferred_locations") as HTMLInputElement
      ).value
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean),
      work_arrangements: [
        ...form.querySelectorAll<HTMLInputElement>(
          "[name=work_arrangements]:checked",
        ),
      ].map((v) => v.value),
      employment_history: readEmployment(list),
    };
    const response = await fetch("/api/v1/candidate/profile", {
      method: "PATCH",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/merge-patch+json",
        "If-Match": etag.value,
        "Idempotency-Key": crypto.randomUUID(),
        "X-CSRFToken": decodeURIComponent(cookie("__Host-enter_csrf")),
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      errors.hidden = false;
      errors.replaceChildren();
      const message = document.createElement("p");
      message.textContent = data.title ?? "Unable to save.";
      errors.append(message);
      if (response.status === 409 && data.current && data.attempted) {
        const reconciliation = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent =
          "Review the latest saved values and your attempted changes";
        const current = document.createElement("pre");
        current.textContent = `Latest saved values\n${JSON.stringify(data.current, null, 2)}`;
        const attempted = document.createElement("pre");
        attempted.textContent = `Your attempted changes\n${JSON.stringify(data.attempted, null, 2)}`;
        reconciliation.append(summary, current, attempted);
        errors.append(reconciliation);
        if (data.current_etag) etag.value = data.current_etag;
      }
      errors.focus();
      status.textContent = "";
      return;
    }
    etag.value = response.headers.get("ETag") ?? etag.value;
    const visibility =
      form.querySelector<HTMLInputElement>("[name=visibility]:checked")
        ?.value ?? "NOT_LOOKING";
    const visibilityPayload: Record<string, unknown> = {
      mode: visibility,
      consent_record_id: crypto.randomUUID(),
    };
    if (visibility === "APPROVED_RECRUITERS") {
      visibilityPayload.approved_tenant_ids = (
        form.elements.namedItem("approved_tenant_ids") as HTMLInputElement
      ).value
        .split(",")
        .map((v) => v.trim())
        .filter(Boolean);
    }
    if (visibility === "MATCHING_ROLES") {
      visibilityPayload.matching_preferences = {
        roles: payload.role_categories,
        locations: payload.preferred_locations,
        work_arrangements: payload.work_arrangements,
      };
    }
    const visibilityResponse = await fetch("/api/v1/candidate/visibility", {
      method: "PUT",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "If-Match": etag.value,
        "Idempotency-Key": crypto.randomUUID(),
        "X-CSRFToken": decodeURIComponent(cookie("__Host-enter_csrf")),
      },
      body: JSON.stringify(visibilityPayload),
    });
    if (!visibilityResponse.ok) {
      errors.hidden = false;
      errors.textContent = "Profile saved, but visibility needs correction.";
      errors.focus();
      status.textContent = "";
      return;
    }
    etag.value = visibilityResponse.headers.get("ETag") ?? etag.value;
    status.textContent = "Profile and visibility saved.";
  });
  root.querySelector("[data-publish]")?.addEventListener("click", async () => {
    status.textContent = "Publishing…";
    const response = await fetch("/api/v1/candidate/profile/publish", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "If-Match": etag.value,
        "Idempotency-Key": crypto.randomUUID(),
        "X-CSRFToken": decodeURIComponent(cookie("__Host-enter_csrf")),
      },
    });
    status.textContent = response.ok
      ? "Profile publication saved."
      : "Profile needs more information before publication.";
  });
  void load();
}
