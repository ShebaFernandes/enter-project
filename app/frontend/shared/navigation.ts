const signOut = document.querySelector<HTMLButtonElement>("[data-sign-out]");
const csrf = () =>
  document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")
    ?.value ?? "";
signOut?.addEventListener("click", async () => {
  if (signOut.disabled) return;
  signOut.disabled = true;
  document.getElementById("sign-out-error")?.remove();
  try {
    const response = await fetch("/api/v1/session/sign-out", {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf() },
    });
    if (!response.ok) throw new Error("Sign-out unavailable");
    sessionStorage.clear();
    location.replace("/");
  } catch {
    signOut.disabled = false;
    const error = document.createElement("p");
    error.id = "sign-out-error";
    error.setAttribute("role", "alert");
    error.textContent = "Sign-out failed. Try again.";
    signOut.after(error);
  }
});
