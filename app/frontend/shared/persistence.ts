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

/**
 * Private notes and recruiting reasons are deliberately never written to browser storage.
 * Successful saves survive refresh through the authorized API; unsaved values receive a
 * navigation warning and remain in the form after recoverable request failures.
 */
export function warnOnUnsaved(forms: HTMLFormElement[]): () => void {
  const listener = (event: BeforeUnloadEvent) => {
    if (forms.some((form) => form.dataset.dirty === "true")) {
      event.preventDefault();
    }
  };
  window.addEventListener("beforeunload", listener);
  return () => window.removeEventListener("beforeunload", listener);
}
// Recruiter drafts stay in memory/DOM only; never persist protected search state.
const form = document.querySelector<HTMLFormElement>("[data-search-form]");
if (form) {
  for (const key of [
    "recruiter-search-draft-v1",
    "enter.criteria-review.v1",
    "enter.confirmed-search.v1",
    "enter.comparison-selection.v1",
    "enter.comparison-return-focus.v1",
  ]) {
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);
  }
  let dirty = false;
  let intentional = false;
  form.addEventListener("input", () => {
    dirty = true;
  });
  window.addEventListener("recruiter-search-intentional-navigation", () => {
    intentional = true;
  });
  window.addEventListener("beforeunload", (event) => {
    if (dirty && !intentional) event.preventDefault();
  });
}
