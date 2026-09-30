export type ConflictPayload = {
  current: Record<string, unknown>;
  attempted: Record<string, unknown>;
  changed_fields: string[];
  current_etag: string;
};

export function showConflict(
  root: HTMLElement,
  conflict: ConflictPayload,
): void {
  const region = root.querySelector<HTMLElement>("[data-conflict]");
  if (!region) return;
  region.hidden = false;
  region.innerHTML = "";
  const heading = document.createElement("h2");
  heading.textContent = "A newer version is available";
  const explanation = document.createElement("p");
  explanation.textContent =
    "Nothing was overwritten. Review the stored and attempted values, then discard or reapply your change.";
  const list = document.createElement("dl");
  conflict.changed_fields.forEach((field) => {
    const term = document.createElement("dt");
    term.textContent = field.replaceAll("_", " ");
    const detail = document.createElement("dd");
    detail.textContent = `Stored: ${String(conflict.current[field] ?? "empty")}; attempted: ${String(conflict.attempted[field] ?? "empty")}`;
    list.append(term, detail);
  });
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.textContent = "Use stored version";
  dismiss.addEventListener("click", () => {
    region.hidden = true;
    root.dataset.etag = conflict.current_etag;
    root.dispatchEvent(
      new CustomEvent("recruiter-conflict-discarded", { detail: conflict }),
    );
  });
  region.append(heading, explanation, list, dismiss);
  region.focus();
}
