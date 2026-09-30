const signOut = document.querySelector<HTMLButtonElement>("[data-sign-out]");
const csrf = () =>
  document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith("__Host-enter_csrf="))
    ?.split("=")[1] ?? "";
signOut?.addEventListener("click", async () => {
  await fetch("/api/v1/session/sign-out", {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrf() },
  });
  sessionStorage.clear();
  location.replace("/api/v1/auth/login");
});
