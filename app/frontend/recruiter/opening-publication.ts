type Transport = (path: string, options?: RequestInit) => Promise<Response>;
type Preview = {
  internal_state: string;
  publication_state: "PUBLISHED" | "UNPUBLISHED";
  public_fields: Record<string, string | null>;
  public_url: string | null;
  source_etag: string;
  preview_digest: string;
};
const fields = {
  id: "Public identifier",
  title: "Job title",
  description: "Public role description",
  location: "Public location",
  work_mode: "Work arrangement",
  employment_type: "Employment type",
  published_at: "Publication time",
  closes_at: "Closing time",
  application_url: "Application URL",
};
function button(label: string, handler: () => void): HTMLButtonElement {
  const control = document.createElement("button");
  control.type = "button";
  control.textContent = label;
  control.addEventListener("click", handler);
  return control;
}
function failure(response: Response): string {
  if (response.status === 409)
    return "This opening or preview changed. Select Preview again before confirming.";
  if ([401, 403, 404].includes(response.status))
    return "Publication is unavailable. Your access may have changed.";
  if (response.status === 422)
    return "Publication was not changed. Check the opening is active and review a fresh preview.";
  return "Publication could not be verified. Refresh the preview to check its current state before retrying.";
}
export function publicationControls(
  opening: { id: string; title: string; state: string },
  request: Transport,
): HTMLLIElement {
  const card = document.createElement("li");
  card.dataset.openingPublication = opening.id;
  const heading = document.createElement("h3");
  heading.textContent = opening.title;
  const internal = document.createElement("p");
  internal.textContent = `Internal state: ${opening.state}`;
  const publication = document.createElement("p");
  publication.textContent = "Public publication: loading…";
  const status = document.createElement("p");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  const details = document.createElement("dl");
  details.hidden = true;
  const link = document.createElement("a");
  link.textContent = "View public role";
  link.hidden = true;
  const path = `/openings/${opening.id}/publication`;
  let current: Preview | null = null;
  let reviewed = false;
  const render = (value: Preview) => {
    current = value;
    internal.textContent = `Internal state: ${value.internal_state}`;
    publication.textContent = `Public publication: ${value.publication_state}`;
    link.hidden = !value.public_url;
    if (value.public_url) link.href = value.public_url;
    publish.textContent =
      value.publication_state === "PUBLISHED"
        ? "Update publication"
        : "Publish";
    publish.disabled = !reviewed || value.internal_state !== "OPEN";
    withdraw.disabled = value.publication_state !== "PUBLISHED";
    activate.hidden = !["DRAFT", "PAUSED"].includes(value.internal_state);
  };
  const load = async (showFields: boolean) => {
    reviewed = false;
    publish.disabled = withdraw.disabled = true;
    status.textContent = "Loading publication status…";
    try {
      const response = await request(path);
      if (!response.ok) throw new Error(failure(response));
      const value = (await response.json()) as Preview;
      reviewed = showFields;
      render(value);
      details.replaceChildren();
      for (const [key, label] of Object.entries(fields)) {
        const term = document.createElement("dt");
        term.textContent = label;
        const description = document.createElement("dd");
        description.textContent =
          value.public_fields[key] ||
          (key === "published_at"
            ? "Assigned by the server when confirmed"
            : "Not provided");
        details.append(term, description);
      }
      details.hidden = !showFields;
      status.textContent = showFields
        ? "Preview ready. Only the fields shown here will be public. Publication requires confirmation."
        : "Publication status loaded.";
    } catch (error) {
      current = null;
      publication.textContent = "Public publication: unavailable";
      link.hidden = details.hidden = true;
      status.textContent =
        error instanceof Error ? error.message : "Publication unavailable.";
    }
  };
  const confirm = (
    action: "publish" | "withdraw",
    trigger: HTMLButtonElement,
  ) => {
    if (!current || (action === "publish" && !reviewed)) return;
    const snapshot = current;
    const dialog = document.createElement("dialog");
    const title = document.createElement("h4");
    title.id = `publication-confirm-${opening.id}`;
    title.textContent =
      action === "publish"
        ? "Confirm public publication"
        : "Confirm public withdrawal";
    dialog.setAttribute("aria-labelledby", title.id);
    const explanation = document.createElement("p");
    explanation.textContent =
      action === "publish"
        ? "Publish the reviewed fields to anyone visiting the public jobs directory?"
        : "Remove this role from public discovery immediately? Its internal opening state will not change.";
    const cancel = button("Cancel", () => dialog.close());
    cancel.autofocus = true;
    const approve = button(
      action === "publish" ? "Confirm publication" : "Confirm withdrawal",
      () => {
        approve.disabled = true;
        dialog.close();
        reviewed = false;
        publish.disabled = withdraw.disabled = true;
        status.textContent = "Saving publication decision…";
        void (async () => {
          try {
            const response = await request(`${path}/${action}`, {
              method: "POST",
              headers: { "If-Match": snapshot.source_etag },
              body: JSON.stringify({
                confirmed: true,
                ...(action === "publish"
                  ? { preview_digest: snapshot.preview_digest }
                  : {}),
              }),
            });
            if (!response.ok) throw new Error(failure(response));
            render((await response.json()) as Preview);
            details.hidden = true;
            status.textContent =
              action === "publish"
                ? "Publication saved. This role is now public."
                : "Publication withdrawn. Internal opening state unchanged.";
          } catch (error) {
            status.textContent =
              error instanceof Error
                ? error.message
                : "Publication unavailable.";
          }
          preview.focus();
        })();
      },
    );
    dialog.append(title, explanation, cancel, approve);
    dialog.addEventListener(
      "close",
      () => {
        dialog.remove();
        trigger.focus();
      },
      { once: true },
    );
    card.append(dialog);
    dialog.showModal();
  };
  const preview = button("Preview", () => {
    void load(true);
  });
  const publish = button("Publish", () => confirm("publish", publish));
  const withdraw = button("Withdraw publication", () =>
    confirm("withdraw", withdraw),
  );
  const activate = button("Open internally (does not publish)", () => {
    if (!current) return;
    activate.disabled = true;
    void request(`/openings/${opening.id}`, {
      method: "PATCH",
      headers: { "If-Match": current.source_etag },
      body: JSON.stringify({ state: "OPEN" }),
    })
      .then(async (response) => {
        if (!response.ok) {
          status.textContent = failure(response);
          return;
        }
        await load(false);
        status.textContent =
          "Opening is internally OPEN and remains unpublished. Preview to publish.";
      })
      .catch(() => {
        status.textContent =
          "Opening state could not be verified. Refresh the preview.";
      })
      .finally(() => {
        activate.disabled = false;
      });
  });
  activate.hidden = true;
  publish.disabled = withdraw.disabled = true;
  card.append(
    heading,
    internal,
    publication,
    link,
    details,
    preview,
    publish,
    withdraw,
    activate,
    status,
  );
  void load(false);
  return card;
}
