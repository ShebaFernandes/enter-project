import { clearDraft, loadDraft, saveDraft } from "../shared/persistence";

type CandidateStatus =
  | "APPLIED"
  | "PROFILE_VIEWED"
  | "SHORTLISTED"
  | "RECRUITER_INTERESTED"
  | "INTERVIEW_REQUESTED"
  | "OFFER_MADE"
  | "NOT_SELECTED"
  | "WITHDRAWN";
type Application = {
  id: string;
  opening_title: string;
  candidate_status: CandidateStatus;
  status_updated_at: string;
  notification_preferences: { email: boolean; whatsapp: boolean };
  notification_states: Array<{
    channel: string;
    state: "PENDING" | "SENT" | "FAILED" | "CANCELLED";
  }>;
  status_history: Array<{
    candidate_status: CandidateStatus;
    updated_at: string;
  }>;
  version: number;
};

const labels: Record<CandidateStatus, string> = {
  APPLIED: "Applied",
  PROFILE_VIEWED: "Profile viewed",
  SHORTLISTED: "Shortlisted",
  RECRUITER_INTERESTED: "Recruiter interested",
  INTERVIEW_REQUESTED: "Interview requested",
  OFFER_MADE: "Offer made",
  NOT_SELECTED: "Not selected",
  WITHDRAWN: "Withdrawn",
};
const root = document.querySelector<HTMLElement>("[data-progress-page]");
if (root) {
  const list = root.querySelector<HTMLElement>("[data-application-list]")!;
  const pageStatus = root.querySelector<HTMLElement>("[data-progress-status]")!;
  const template = document.querySelector<HTMLTemplateElement>(
    "#application-card-template",
  )!;
  const csrf = () =>
    document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
      ?.value ?? "";
  const render = async () => {
    const response = await fetch("/api/v1/candidate/applications");
    if (!response.ok) {
      pageStatus.textContent =
        "Applications are temporarily unavailable. Try again safely.";
      return;
    }
    const applications = (await response.json()) as Application[];
    list.replaceChildren();
    pageStatus.textContent = applications.length
      ? ""
      : "You have no applications yet.";
    for (const application of applications) {
      const card = template.content.firstElementChild!.cloneNode(
        true,
      ) as HTMLElement;
      card.dataset.applicationId = application.id;
      card.querySelector<HTMLElement>("[data-role-title]")!.textContent =
        application.opening_title;
      card.querySelector<HTMLElement>("[data-current-status]")!.textContent =
        labels[application.candidate_status];
      const time = card.querySelector<HTMLTimeElement>("[data-status-time]")!;
      time.dateTime = application.status_updated_at;
      time.textContent = new Date(application.status_updated_at).toLocaleString(
        "en-IN",
      );
      const history = card.querySelector<HTMLOListElement>(
        "[data-status-history]",
      )!;
      for (const event of application.status_history) {
        const item = document.createElement("li");
        item.textContent = `${labels[event.candidate_status]} — ${new Date(event.updated_at).toLocaleString("en-IN")}`;
        history.append(item);
      }
      const deliveryList =
        card.querySelector<HTMLUListElement>("[data-deliveries]")!;
      for (const delivery of application.notification_states) {
        const item = document.createElement("li");
        item.textContent = `${delivery.channel}: ${delivery.state.toLowerCase()}`;
        deliveryList.append(item);
      }
      const form = card.querySelector<HTMLFormElement>(
        "[data-preferences-form]",
      )!;
      const email = form.elements.namedItem("email") as HTMLInputElement;
      const whatsapp = form.elements.namedItem("whatsapp") as HTMLInputElement;
      const draftKey = `application-preferences:${application.id}`;
      const draft = loadDraft<{ email: boolean; whatsapp: boolean }>(draftKey);
      email.checked =
        draft?.email ?? application.notification_preferences.email;
      whatsapp.checked =
        draft?.whatsapp ?? application.notification_preferences.whatsapp;
      form.addEventListener("input", () =>
        saveDraft(draftKey, {
          email: email.checked,
          whatsapp: whatsapp.checked,
        }),
      );
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const current = await fetch(
          `/api/v1/candidate/applications/${application.id}`,
        );
        const response = await fetch(
          `/api/v1/candidate/applications/${application.id}/notification-preferences`,
          {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              "If-Match": current.headers.get("ETag") ?? "",
              "Idempotency-Key": crypto.randomUUID(),
              "X-CSRFToken": csrf(),
            },
            body: JSON.stringify({
              email: email.checked,
              whatsapp: whatsapp.checked,
            }),
          },
        );
        card.querySelector<HTMLElement>("[data-card-status]")!.textContent =
          response.ok
            ? "Update channels saved."
            : response.status === 409
              ? "Your application changed elsewhere. Review the latest values and retry."
              : "Channels were not changed. Try again.";
        if (response.ok) clearDraft(draftKey);
      });
      card
        .querySelector<HTMLButtonElement>("[data-withdraw]")!
        .addEventListener("click", async () => {
          if (
            !window.confirm(
              "Withdraw only this application? Other applications will not change.",
            )
          )
            return;
          const current = await fetch(
            `/api/v1/candidate/applications/${application.id}`,
          );
          const response = await fetch(
            `/api/v1/candidate/applications/${application.id}/withdraw`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "If-Match": current.headers.get("ETag") ?? "",
                "Idempotency-Key": crypto.randomUUID(),
                "X-CSRFToken": csrf(),
              },
              body: JSON.stringify({
                candidate_status: "WITHDRAWN",
                confirm: true,
              }),
            },
          );
          card.querySelector<HTMLElement>("[data-card-status]")!.textContent =
            response.ok
              ? "This application is withdrawn."
              : response.status === 409
                ? "Your application changed elsewhere. Review and confirm again."
                : "Withdrawal failed; nothing changed.";
          if (response.ok) await render();
        });
      list.append(card);
    }
  };
  void render();
}
