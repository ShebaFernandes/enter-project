import { sameOriginClient, responseJson } from "./api-client";

export type HandoffKind =
  | "criteria-review"
  | "search-results"
  | "comparison-selection";

/** The fragment is never sent in HTTP URLs or referrers. No browser persistence. */
export function handoffToken(): string | null {
  const token = new URLSearchParams(location.hash.slice(1)).get("handoff");
  return token && /^[A-Za-z0-9_-]{43}$/.test(token) ? token : null;
}

export function workflowTransport(tenantId: string) {
  const client = sameOriginClient({
    tenantId,
    csrfToken: () =>
      document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
        ?.value ?? "",
  });
  const endpoint = (kind: HandoffKind) =>
    `/api/v1/tenants/${tenantId}/search-handoffs/${kind}`;
  return {
    client,
    async create(
      kind: HandoffKind,
      payload: object,
      retryKey = crypto.randomUUID(),
    ) {
      const { data } = await responseJson<{ token: string }>(
        await client(endpoint(kind), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": retryKey,
          },
          body: JSON.stringify(payload),
        }),
      );
      return data.token;
    },
    async restore<T>(
      kind: HandoffKind,
      token: string,
      display = false,
    ): Promise<T> {
      const { data } = await responseJson<T>(
        await client(endpoint(kind) + (display ? "/display" : ""), {
          headers: { "X-Workflow-Handoff": token },
        }),
      );
      return data;
    },
    async revise<T>(token: string, etag: string, criteria: object): Promise<T> {
      const { data } = await responseJson<T>(
        await client(endpoint("criteria-review"), {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "X-Workflow-Handoff": token,
            "If-Match": etag,
          },
          body: JSON.stringify({ criteria }),
        }),
      );
      return data;
    },
    navigate(kind: HandoffKind, token: string) {
      const path =
        kind === "criteria-review" ? "criteria-review/" : "?view=results";
      window.dispatchEvent(
        new Event("recruiter-search-intentional-navigation"),
      );
      location.assign(
        `/tenants/${tenantId}/recruiter/search/${path}#handoff=${encodeURIComponent(token)}`,
      );
    },
  };
}
