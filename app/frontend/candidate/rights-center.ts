const rightsRoot = document.querySelector<HTMLElement>("[data-rights-center]");

if (rightsRoot) {
  const list = rightsRoot.querySelector<HTMLElement>("[data-rights-list]")!;
  const status = rightsRoot.querySelector<HTMLElement>("[data-rights-status]")!;
  const dialog = rightsRoot.querySelector<HTMLDialogElement>(
    "[data-deletion-dialog]",
  )!;
  const escalationDialog = rightsRoot.querySelector<HTMLDialogElement>(
    "[data-escalation-dialog]",
  )!;
  let escalationRequestId = "";
  const csrf = () =>
    decodeURIComponent(
      document.cookie
        .split(";")
        .map((v) => v.trim())
        .find((v) => v.startsWith("__Host-enter_csrf="))
        ?.split("=")[1] ?? "",
    );
  const refresh = async () => {
    const response = await fetch("/api/v1/candidate/rights-requests", {
      credentials: "same-origin",
    });
    if (!response.ok) return;
    const data = await response.json();
    list.replaceChildren();
    for (const item of data) {
      const article = document.createElement("article");
      const heading = document.createElement("h3");
      heading.textContent = item.request_type.replaceAll("_", " ");
      const detail = document.createElement("p");
      detail.textContent = `${item.state} — expected by ${new Date(item.expected_completion_at).toLocaleString()}`;
      article.append(heading, detail);
      if (item.safe_detail) {
        const safeDetail = document.createElement("p");
        safeDetail.textContent = item.safe_detail;
        article.append(safeDetail);
      }
      if (item.exception_scope) {
        const heldScope = document.createElement("p");
        heldScope.textContent = `Retained scope: ${JSON.stringify(item.exception_scope)}`;
        article.append(heldScope);
      }
      if (item.request_type === "EXPORT" && item.state === "COMPLETED") {
        if (item.completed_at) {
          const expiry = document.createElement("p");
          const expiresAt = new Date(item.completed_at);
          expiresAt.setHours(expiresAt.getHours() + 24);
          expiry.textContent = `Download expires ${expiresAt.toLocaleString()}.`;
          article.append(expiry);
        }
        const download = document.createElement("button");
        download.type = "button";
        download.textContent = "Download export";
        download.addEventListener("click", async () => {
          const downloadResponse = await fetch(
            `/api/v1/candidate/rights-requests/${item.id}/download`,
            {
              method: "POST",
              credentials: "same-origin",
              headers: {
                "Idempotency-Key": crypto.randomUUID(),
                "X-CSRFToken": csrf(),
              },
            },
          );
          if (!downloadResponse.ok) {
            status.textContent = "The export is unavailable or has expired.";
            return;
          }
          const blob = new Blob(
            [JSON.stringify(await downloadResponse.json(), null, 2)],
            { type: "application/json" },
          );
          const anchor = document.createElement("a");
          anchor.href = URL.createObjectURL(blob);
          anchor.download = `candidate-data-${item.id}.json`;
          anchor.click();
          URL.revokeObjectURL(anchor.href);
          status.textContent = "Export download prepared.";
        });
        article.append(download);
      }
      if (item.support_escalation_available) {
        const support = document.createElement("button");
        support.type = "button";
        support.textContent = "Ask privacy support for help";
        support.addEventListener("click", () => {
          escalationRequestId = item.id;
          escalationDialog.showModal();
        });
        article.append(support);
      }
      list.append(article);
    }
  };
  const submit = async (payload: object) => {
    status.textContent = "Submitting request…";
    const response = await fetch("/api/v1/candidate/rights-requests", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
        "X-CSRFToken": csrf(),
      },
      body: JSON.stringify(payload),
    });
    status.textContent = response.ok
      ? "Request recorded."
      : "The request could not be completed.";
    if (response.ok) await refresh();
  };
  rightsRoot
    .querySelectorAll<HTMLButtonElement>("[data-right]")
    .forEach((button) =>
      button.addEventListener("click", () => {
        if (button.dataset.right === "DELETE") dialog.showModal();
        else void submit({ request_type: button.dataset.right });
      }),
    );
  rightsRoot
    .querySelector("[data-cancel-delete]")
    ?.addEventListener("click", () => dialog.close());
  rightsRoot
    .querySelector("[data-confirm-delete]")
    ?.addEventListener("click", () => {
      const proof = dialog.querySelector<HTMLInputElement>(
        "[name=step_up_proof]",
      )!.value;
      void submit({
        request_type: "DELETE",
        confirm_consequences: true,
        step_up_proof: proof,
      });
      dialog.close();
    });
  rightsRoot
    .querySelector("[data-cancel-escalation]")
    ?.addEventListener("click", () => escalationDialog.close());
  rightsRoot
    .querySelector("[data-confirm-escalation]")
    ?.addEventListener("click", async () => {
      const reason = escalationDialog
        .querySelector<HTMLTextAreaElement>("[name=escalation_reason]")!
        .value.trim();
      if (!reason) {
        status.textContent = "Provide a reason before escalating.";
        return;
      }
      const response = await fetch(
        `/api/v1/candidate/rights-requests/${escalationRequestId}/escalations`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
            "X-CSRFToken": csrf(),
          },
          body: JSON.stringify({ reason }),
        },
      );
      status.textContent = response.ok
        ? "Privacy support escalation recorded."
        : "The escalation could not be recorded.";
      if (response.ok) escalationDialog.close();
    });
  void refresh();
}
