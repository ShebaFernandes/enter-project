/** Transport only. Django decides authentication, authorization and validation. */
export function sameOriginClient(context: {
  tenantId?: string;
  csrfToken: () => string;
}) {
  return (input: string, init: RequestInit = {}): Promise<Response> => {
    const url = new URL(input, location.origin);
    if (
      url.origin !== location.origin ||
      url.username ||
      url.password ||
      !url.pathname.startsWith("/api/v1/")
    )
      throw new Error("Request outside the API origin");
    const pathTenant = url.pathname.match(
      /^\/api\/v1\/tenants\/([^/]+)\//,
    )?.[1];
    if (pathTenant && pathTenant !== context.tenantId)
      throw new Error("Request outside the current tenant context");
    const headers = new Headers(init.headers);
    headers.delete("X-Tenant-ID");
    if (context.tenantId) headers.set("X-Tenant-ID", context.tenantId);
    if (
      !["GET", "HEAD", "OPTIONS"].includes((init.method ?? "GET").toUpperCase())
    )
      headers.set("X-CSRFToken", context.csrfToken());
    return fetch(url.href, {
      ...init,
      headers,
      credentials: "same-origin",
      redirect: "error",
      cache: "no-store",
    });
  };
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly etag: string | null,
  ) {
    super(
      status === 409
        ? "Information changed. Review before resubmitting."
        : "Unable to complete the request.",
    );
  }
}
export async function responseJson<T>(
  response: Response,
): Promise<{ data: T; etag: string | null }> {
  const etag = response.headers.get("ETag");
  if (!response.ok) throw new ApiError(response.status, etag);
  return { data: (await response.json()) as T, etag };
}
