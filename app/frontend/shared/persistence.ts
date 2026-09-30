type Draft = {
  prompt: string;
  context: string;
  openingId: string;
  criteria: Record<string, string>[];
  filter: string;
  selection: string;
};

export function saveDraft<T>(key: string, value: T): void {
  sessionStorage.setItem(key, JSON.stringify(value));
}

export function loadDraft<T>(key: string): T | null {
  try {
    return JSON.parse(sessionStorage.getItem(key) ?? "null") as T | null;
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

export function clearDraft(key: string): void {
  sessionStorage.removeItem(key);
}
const persisted = document.querySelector<HTMLFormElement>("[data-search-form]");
if (persisted) {
  const key = "recruiter-search-draft-v1";
  let intentionalNavigation = false;
  const root = persisted.closest<HTMLElement>("[data-recruiter-search]")!;
  const fields = ["purpose", "group_operator", "field", "operator", "value"];
  const read = (): Draft => ({
    prompt: (persisted.elements.namedItem("prompt") as HTMLTextAreaElement)
      .value,
    context: (persisted.elements.namedItem("context") as HTMLSelectElement)
      .value,
    openingId: (persisted.elements.namedItem("opening_id") as HTMLInputElement)
      .value,
    criteria: [
      ...root.querySelectorAll<HTMLElement>("[data-criterion-id]"),
    ].map((row) =>
      Object.fromEntries(
        fields.map((name) => [
          name,
          row.querySelector<HTMLInputElement | HTMLSelectElement>(
            `[name=${name}]`,
          )?.value ?? "",
        ]),
      ),
    ),
    filter:
      root.querySelector<HTMLButtonElement>("[data-filter][aria-pressed=true]")
        ?.dataset.filter ?? "all",
    selection: root.dataset.selectedCandidate ?? "",
  });
  const save = () => sessionStorage.setItem(key, JSON.stringify(read()));
  try {
    const draft = JSON.parse(
      sessionStorage.getItem(key) ?? "null",
    ) as Draft | null;
    if (draft) {
      (persisted.elements.namedItem("prompt") as HTMLTextAreaElement).value =
        draft.prompt;
      const context = persisted.elements.namedItem(
        "context",
      ) as HTMLSelectElement;
      context.value = draft.context;
      context.dispatchEvent(new Event("change"));
      (persisted.elements.namedItem("opening_id") as HTMLInputElement).value =
        draft.openingId;
      while (
        root.querySelectorAll("[data-criterion-id]").length <
        draft.criteria.length
      )
        root.querySelector<HTMLButtonElement>("[data-add-criterion]")?.click();
      root
        .querySelectorAll<HTMLElement>("[data-criterion-id]")
        .forEach((row, index) =>
          fields.forEach((name) => {
            const input = row.querySelector<
              HTMLInputElement | HTMLSelectElement
            >(`[name=${name}]`);
            if (input && draft.criteria[index])
              input.value = draft.criteria[index][name] ?? input.value;
          }),
        );
      root
        .querySelector<HTMLButtonElement>(`[data-filter="${draft.filter}"]`)
        ?.click();
      root.dataset.selectedCandidate = draft.selection;
    }
  } catch {
    sessionStorage.removeItem(key);
  }
  persisted.addEventListener("input", save);
  persisted.addEventListener("change", save);
  root.addEventListener("click", (event) => {
    if (
      (event.target as HTMLElement).closest(
        "[data-filter], [data-add-criterion], [data-criterion-id] button",
      )
    )
      queueMicrotask(save);
  });
  window.addEventListener("recruiter-search-selection", ((
    event: CustomEvent<string>,
  ) => {
    root.dataset.selectedCandidate = event.detail;
    save();
  }) as EventListener);
  window.addEventListener("recruiter-search-intentional-navigation", () => {
    intentionalNavigation = true;
  });
  window.addEventListener("beforeunload", (event) => {
    if (
      !intentionalNavigation &&
      (read().prompt.trim() || read().criteria.some((item) => item.value))
    )
      event.preventDefault();
  });
}
