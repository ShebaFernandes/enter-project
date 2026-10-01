import { Component, type ComponentType, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { sameOriginClient } from "../shared/api-client";

export type PageBootstrap = {
  version: 1;
  page: string;
  tenantId?: string;
  candidateId?: string;
  requiresSession: boolean;
  entryError?: boolean;
};
export type PageProps = {
  bootstrap: PageBootstrap;
  request: ReturnType<typeof sameOriginClient>;
};
export function readBootstrap(element: HTMLElement): PageBootstrap {
  if (
    element.tagName !== "SCRIPT" ||
    element.getAttribute("type") !== "application/json"
  )
    throw new Error("Invalid bootstrap element");
  const value = JSON.parse(element.textContent ?? "") as Partial<PageBootstrap>;
  if (
    !value ||
    value.version !== 1 ||
    typeof value.page !== "string" ||
    typeof value.requiresSession !== "boolean" ||
    (value.entryError !== undefined && typeof value.entryError !== "boolean") ||
    (value.candidateId !== undefined &&
      (typeof value.candidateId !== "string" ||
        !/^[a-f0-9-]{36}$/i.test(value.candidateId))) ||
    (value.tenantId !== undefined &&
      (typeof value.tenantId !== "string" ||
        !/^[a-f0-9-]{36}$/i.test(value.tenantId)))
  )
    throw new Error("Invalid page bootstrap");
  return {
    version: 1,
    page: value.page,
    requiresSession: value.requiresSession,
    ...(value.entryError ? { entryError: true } : {}),
    ...(value.tenantId ? { tenantId: value.tenantId } : {}),
    ...(value.candidateId ? { candidateId: value.candidateId } : {}),
  };
}
class PageBoundary extends Component<
  { children: ReactNode; onFailure: () => void },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFailure();
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
/** Register components in reviewed page entry modules, never from a URL/storage flag. */
export async function mountPage(
  pages: Readonly<Record<string, ComponentType<PageProps>>>,
): Promise<() => void> {
  const root = document.querySelector<HTMLElement>("[data-react-page]");
  const fallback = document.querySelector<HTMLElement>("[data-page-fallback]");
  const json = document.getElementById("page-bootstrap");
  if (
    !root ||
    !fallback ||
    !json ||
    document.body.dataset.frontendRenderer !== "react" ||
    root.childElementCount ||
    root.closest("main") ||
    root.dataset.owner ||
    document.querySelector('script[src$="/dist/assets/app.js"]')
  )
    throw new Error("Exclusive React page ownership required");
  const bootstrap = readBootstrap(json);
  const Page = pages[bootstrap.page];
  if (!Page) throw new Error("Unregistered page");
  const abort = new AbortController();
  const transport = sameOriginClient({
    tenantId: bootstrap.tenantId,
    csrfToken: () =>
      document.querySelector<HTMLInputElement>(
        "[data-page-csrf] [name=csrfmiddlewaretoken]",
      )?.value ?? "",
  });
  const request: ReturnType<typeof sameOriginClient> = (input, init = {}) =>
    transport(input, {
      ...init,
      signal: init.signal
        ? AbortSignal.any([init.signal, abort.signal])
        : abort.signal,
    });
  let mounted: Root | undefined;
  root.dataset.owner = "react-pending";
  const failure = () => {
    fallback.hidden = false;
    root.hidden = true;
    fallback.focus();
  };
  const dispose = () => {
    abort.abort();
    mounted?.unmount();
    mounted = undefined;
    delete root.dataset.owner;
    fallback.hidden = false;
  };
  window.addEventListener("pagehide", dispose, { once: true });
  try {
    if (bootstrap.requiresSession) {
      const response = await request("/api/v1/session");
      if (!response.ok) throw new Error("Current session unavailable");
      // Every subsequent API reauthorizes; no role/object policy is reproduced here.
    }
    abort.signal.throwIfAborted();
    root.classList.add("enter-ui");
    root.hidden = false;
    root.dataset.owner = "react";
    mounted = createRoot(root, {
      onCaughtError: () => {},
      onUncaughtError: failure,
    });
    mounted.render(
      <PageBoundary onFailure={failure}>
        <Page bootstrap={bootstrap} request={request} />
      </PageBoundary>,
    );
    fallback.hidden = true;
  } catch (error) {
    window.removeEventListener("pagehide", dispose);
    dispose();
    throw error;
  }
  const onShow = (event: PageTransitionEvent) => {
    if (event.persisted) location.reload();
  };
  window.addEventListener("pageshow", onShow);
  return () => {
    window.removeEventListener("pagehide", dispose);
    window.removeEventListener("pageshow", onShow);
    dispose();
  };
}
