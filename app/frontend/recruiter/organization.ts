type OrganizationRoot = HTMLElement & { dataset: { tenantId?: string } };

export {};

function csrf(root: HTMLElement): string {
  return (
    root.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")?.value ??
    ""
  );
}

async function request(
  root: OrganizationRoot,
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  return fetch(`/api/v1/tenants/${root.dataset.tenantId}${path}`, {
    credentials: "same-origin",
    ...options,
    headers: {
      "X-Tenant-ID": root.dataset.tenantId ?? "",
      "X-CSRFToken": csrf(root),
      ...(options.method && options.method !== "GET"
        ? {
            "Idempotency-Key": crypto.randomUUID(),
            "Content-Type": "application/json",
          }
        : {}),
      ...options.headers,
    },
  });
}

function item(text: string): HTMLLIElement {
  const element = document.createElement("li");
  element.textContent = text;
  return element;
}

function values(form: HTMLFormElement): Record<string, FormDataEntryValue> {
  return Object.fromEntries(new FormData(form));
}

document
  .querySelectorAll<OrganizationRoot>("[data-organization]")
  .forEach((root) => {
    const status = root.querySelector<HTMLElement>(
      "[data-organization-status]",
    )!;
    const units = root.querySelector<HTMLElement>("[data-business-unit-list]");
    const openings = root.querySelector<HTMLElement>("[data-opening-list]");
    const synthetic = root.querySelector<HTMLElement>("[data-synthetic-list]");
    const saved = root.querySelector<HTMLElement>("[data-saved-search-list]");

    const load = async () => {
      const unitResponse = await request(root, "/business-units");
      const openingResponse = await request(root, "/openings");
      if (unitResponse.ok && units) {
        const data = (await unitResponse.json()) as {
          id: string;
          name: string;
          status: string;
        }[];
        units.replaceChildren(
          ...data.map((value) =>
            item(`${value.name} — ${value.status} — ${value.id}`),
          ),
        );
      }
      if (openingResponse.ok && openings) {
        const data = (await openingResponse.json()) as {
          id: string;
          title: string;
          state: string;
        }[];
        openings.replaceChildren(
          ...data.map((value) =>
            item(`${value.title} — ${value.state} — ${value.id}`),
          ),
        );
      }
      if (synthetic) {
        const syntheticResponse = await request(
          root,
          "/recruiter-entered-candidates",
        );
        if (!syntheticResponse.ok) return;
        const data = (await syntheticResponse.json()) as {
          display_name: string;
          source_label: string;
        }[];
        synthetic.replaceChildren(
          ...data.map((value) =>
            item(`${value.display_name} — ${value.source_label}`),
          ),
        );
      }
      if (saved) {
        const savedResponse = await request(root, "/saved-searches");
        if (!savedResponse.ok) return;
        const data = (await savedResponse.json()) as {
          name: string;
          criteria: { context: { type: string; opening_id?: string } };
          changed_since_save: string[];
        }[];
        saved.replaceChildren(
          ...data.map((value) => {
            const context = value.criteria.context;
            const changes = value.changed_since_save.length
              ? ` — changed: ${value.changed_since_save.join(", ")}`
              : "";
            return item(
              `${value.name} — ${context.type}${context.opening_id ? ` ${context.opening_id}` : ""}${changes}`,
            );
          }),
        );
      }
    };

    root
      .querySelector<HTMLFormElement>("[data-business-unit-form]")
      ?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget as HTMLFormElement;
        const data = values(form);
        const response = await request(root, "/business-units", {
          method: "POST",
          body: JSON.stringify({
            name: data.name,
            description: data.description,
          }),
        });
        status.textContent = response.ok
          ? "Business unit created."
          : "Business unit was not created.";
        if (response.ok) {
          form.reset();
          await load();
        }
      });

    root
      .querySelector<HTMLFormElement>("[data-opening-form]")
      ?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget as HTMLFormElement;
        const data = values(form);
        const response = await request(root, "/openings", {
          method: "POST",
          body: JSON.stringify({
            business_unit_id: data.business_unit_id,
            title: data.title,
            location: { display: data.location },
            work_mode: data.work_mode,
            employment_type: data.employment_type,
          }),
        });
        status.textContent = response.ok
          ? "Opening created."
          : "Opening was not created.";
        if (response.ok) await load();
      });

    root
      .querySelector<HTMLFormElement>("[data-synthetic-form]")
      ?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget as HTMLFormElement;
        const data = values(form);
        const response = await request(root, "/recruiter-entered-candidates", {
          method: "POST",
          body: JSON.stringify({
            display_name: data.display_name,
            location: { display: data.location },
            experience_years: data.experience_years,
            skills: String(data.skills)
              .split(",")
              .map((value) => value.trim())
              .filter(Boolean),
            confirm_synthetic: data.confirm_synthetic === "on",
          }),
        });
        status.textContent = response.ok
          ? "Synthetic candidate created with immutable provenance."
          : "Synthetic candidate was not created.";
        if (response.ok) await load();
      });

    root
      .querySelector<HTMLFormElement>("[data-saved-search-form]")
      ?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget as HTMLFormElement;
        const data = values(form);
        const response = await request(root, "/saved-searches", {
          method: "POST",
          body: JSON.stringify({ name: data.name, search_id: data.search_id }),
        });
        status.textContent = response.ok
          ? "Search saved."
          : "Search was not saved.";
        if (response.ok) await load();
      });

    void load();
  });
