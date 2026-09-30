const signOut = document.querySelector<HTMLButtonElement>("[data-sign-out]");
const csrf = () =>
  document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
    ?.value ?? "";
signOut?.addEventListener("click", async () => {
  await fetch("/api/v1/session/sign-out", {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrf() },
  });
  sessionStorage.clear();
  location.replace("/api/v1/auth/login");
});
