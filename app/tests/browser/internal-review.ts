import type { Page } from "@playwright/test";

/** Explicit internal fallback coverage; this is not the normal recruiter journey. */
export async function openInternalReview(page: Page) {
  const path = await page.evaluate(async () => {
    const tenant = location.pathname.split("/")[2];
    const base = `/api/v1/tenants/${tenant}`;
    const headers = {
      "Content-Type": "application/json",
      "X-Tenant-ID": tenant,
      "X-CSRFToken": document.querySelector<HTMLInputElement>(
        "[name=csrfmiddlewaretoken]",
      )!.value,
    };
    const response = await fetch(`${base}/searches/interpret`, {
      method: "POST",
      headers,
      body: JSON.stringify({ prompt: "Python", context: { type: "AD_HOC" } }),
    });
    if (!response.ok) throw new Error("Internal fixture interpretation failed");
    const intent = await response.json();
    const created = await fetch(`${base}/search-handoffs/criteria-review`, {
      method: "POST",
      headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({
        workflow_id: intent.workflow_id,
        criteria: intent.criteria,
      }),
    });
    if (!created.ok) throw new Error("Internal fixture handoff failed");
    const handoff = await created.json();
    return `/tenants/${tenant}/recruiter/search/criteria-review/#handoff=${handoff.token}`;
  });
  await page.goto(new URL(path, page.url()).href);
}
