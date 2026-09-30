const speechRoot = document.querySelector<HTMLElement>(
  "[data-recruiter-search]",
);
type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onstart: (() => void) | null;
  onresult:
    | ((event: {
        results: ArrayLike<{ 0: { transcript: string }; isFinal: boolean }>;
      }) => void)
    | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};
if (speechRoot) {
  const button = speechRoot.querySelector<HTMLButtonElement>("[data-speech]")!;
  const output = speechRoot.querySelector<HTMLElement>("[data-speech-status]")!;
  const prompt =
    speechRoot.querySelector<HTMLTextAreaElement>("[name=prompt]")!;
  const Constructor =
    (
      window as unknown as {
        SpeechRecognition?: new () => Recognition;
        webkitSpeechRecognition?: new () => Recognition;
      }
    ).SpeechRecognition ??
    (window as unknown as { webkitSpeechRecognition?: new () => Recognition })
      .webkitSpeechRecognition;
  if (!Constructor) {
    button.disabled = true;
    output.textContent =
      "Speech input is unavailable. Typed search remains fully usable.";
  } else {
    const recognition = new Constructor();
    let listening = false;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-IN";
    recognition.onstart = () => {
      listening = true;
      button.setAttribute("aria-pressed", "true");
      output.textContent = "Listening…";
    };
    recognition.onresult = (event) => {
      output.textContent = "Transcribing…";
      prompt.value = Array.from(event.results)
        .map((r) => r[0].transcript)
        .join("");
      if (Array.from(event.results).every((r) => r.isFinal))
        output.textContent = "Transcript ready. Edit it, then choose Search.";
    };
    recognition.onerror = (event) => {
      listening = false;
      output.textContent =
        event.error === "not-allowed"
          ? "Speech permission was denied. Typed search remains usable."
          : "Speech input failed. Typed search remains usable.";
    };
    recognition.onend = () => {
      listening = false;
      button.setAttribute("aria-pressed", "false");
    };
    button.addEventListener("click", () => {
      if (listening) recognition.stop();
      else recognition.start();
    });
  }
}
