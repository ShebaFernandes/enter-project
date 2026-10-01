import { sameOriginClient } from "./api-client";
/** Transport context from Django bootstrap; server policy remains authoritative. */
export function tenantClient(root: HTMLElement) {
  const tenant = root.dataset.tenantId;
  if (!tenant) throw new Error("Tenant context unavailable");
  const request = sameOriginClient({
    tenantId: tenant,
    csrfToken: () =>
      root.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
        ?.value ?? "",
  });
  return (input: string, init: RequestInit = {}): Promise<Response> => {
    const url = new URL(input, location.origin);
    if (
      url.origin !== location.origin ||
      !url.pathname.startsWith(`/api/v1/tenants/${tenant}/`)
    ) {
      throw new Error("Request outside the current tenant context");
    }
    return request(url.href, init);
  };
}
