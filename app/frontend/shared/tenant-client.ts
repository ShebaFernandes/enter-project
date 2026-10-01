/** Transport context from Django bootstrap; server policy remains authoritative. */
export function tenantClient(root: HTMLElement) {
  const tenant = root.dataset.tenantId;
  if (!tenant) throw new Error("Tenant context unavailable");
  return (input: string, init: RequestInit = {}): Promise<Response> => {
    const url = new URL(input, location.origin);
    if (
      url.origin !== location.origin ||
      !url.pathname.startsWith(`/api/v1/tenants/${tenant}/`)
    ) {
      throw new Error("Request outside the current tenant context");
    }
    const headers = new Headers(init.headers);
    headers.set("X-Tenant-ID", tenant);
    if (!["GET", "HEAD"].includes((init.method ?? "GET").toUpperCase())) {
      headers.set(
        "X-CSRFToken",
        root.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
          ?.value ?? "",
      );
    }
    return fetch(url.href, {
      ...init,
      headers,
      credentials: "same-origin",
      redirect: "error",
    });
  };
}
