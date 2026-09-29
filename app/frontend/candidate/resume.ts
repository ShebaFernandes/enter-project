const resumeInput = document.querySelector<HTMLInputElement>("[data-resume]");
const resumeStatus = document.querySelector<HTMLElement>(
  "[data-resume-status]",
);

function csrfCookie(): string {
  return decodeURIComponent(
    document.cookie
      .split(";")
      .map((v) => v.trim())
      .find((v) => v.startsWith("__Host-enter_csrf="))
      ?.split("=")[1] ?? "",
  );
}

if (resumeInput && resumeStatus) {
  const suggestions = document.querySelector<HTMLElement>(
    "[data-resume-suggestions]",
  );
  const renderState = (state: {
    scan_status: string;
    parse_status: string;
    manual_entry_available?: boolean;
    suggestions?: Array<{
      fact_type?: string;
      value?: unknown;
      confidence?: number | null;
      source_spans?: unknown[];
    }>;
  }) => {
    const terminal = ["REJECTED", "SCAN_FAILED"].includes(state.scan_status);
    if (terminal) {
      resumeStatus.textContent =
        "Security scanning did not succeed. The resume remains unavailable; continue with manual entry.";
    } else if (state.parse_status === "PARSE_FAILED") {
      resumeStatus.textContent =
        "Resume parsing failed. Continue by entering profile and employment facts manually.";
    } else if (["REVIEW_REQUIRED", "READY"].includes(state.parse_status)) {
      resumeStatus.textContent =
        state.parse_status === "READY"
          ? "Resume processing complete."
          : "Review each suggested fact before using it.";
    } else {
      resumeStatus.textContent =
        "Resume is quarantined while security checks continue…";
    }
    if (!suggestions) return;
    suggestions.replaceChildren();
    for (const fact of state.suggestions ?? []) {
      const article = document.createElement("article");
      const heading = document.createElement("h3");
      heading.textContent = String(
        fact.fact_type ?? "Suggested fact",
      ).replaceAll("_", " ");
      const value = document.createElement("p");
      value.textContent = `Suggested value: ${JSON.stringify(fact.value ?? null)}`;
      const evidence = document.createElement("p");
      evidence.textContent = `Confidence: ${fact.confidence ?? "not supplied"}; source spans: ${(fact.source_spans ?? []).length}`;
      article.append(heading, value, evidence);
      suggestions.append(article);
    }
  };
  const poll = async (resumeId: string, remaining = 20): Promise<void> => {
    const response = await fetch(`/api/v1/candidate/resumes/${resumeId}`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      resumeStatus.textContent =
        "Resume status is temporarily unavailable. You can continue with manual entry.";
      return;
    }
    const state = await response.json();
    renderState(state);
    const complete =
      ["REJECTED", "SCAN_FAILED"].includes(state.scan_status) ||
      ["REVIEW_REQUIRED", "READY", "PARSE_FAILED"].includes(state.parse_status);
    if (!complete && remaining > 0) {
      await new Promise((resolve) => window.setTimeout(resolve, 1500));
      await poll(resumeId, remaining - 1);
    }
  };
  resumeInput.addEventListener("change", async () => {
    const file = resumeInput.files?.[0];
    if (!file) {
      resumeStatus.textContent = "No file selected.";
      return;
    }
    resumeStatus.textContent = "Reading and validating file…";
    if (file.size > 10_485_760) {
      resumeStatus.textContent = "File is larger than 10 MB.";
      return;
    }
    const digest = await crypto.subtle.digest(
      "SHA-256",
      await file.arrayBuffer(),
    );
    const sha256 = [...new Uint8Array(digest)]
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
    const response = await fetch("/api/v1/candidate/resumes/uploads", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
        "X-CSRFToken": csrfCookie(),
      },
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
        sha256,
      }),
    });
    if (!response.ok) {
      resumeStatus.textContent =
        "The resume could not be accepted. You can continue with manual entry.";
      return;
    }
    const grant = await response.json();
    resumeStatus.textContent = "Uploading to the secure quarantine area…";
    const upload = await fetch(grant.upload_url, {
      method: "PUT",
      headers: grant.required_headers,
      body: file,
    });
    if (!upload.ok) {
      resumeStatus.textContent =
        "The secure upload failed. You can retry or continue with manual entry.";
      return;
    }
    resumeStatus.textContent =
      "Upload complete. The resume remains private until security scanning succeeds.";
    await poll(grant.resume_id);
  });
}
