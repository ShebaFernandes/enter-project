import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button, Header, SkipLink, StatusMessage, Alert } from "./components";
import type { PageProps } from "./mount";
import type { Recognition } from "../recruiter/speech-search";
import { workflowTransport } from "../shared/workflow-handoff";

type Opening = { id: string; title: string; state: string };
type Recent = { search_id: string; created_at: string; name?: string };
export function SearchHome({ bootstrap, request }: PageProps) {
  const tenant = bootstrap.tenantId!;
  const base = `/api/v1/tenants/${tenant}`;
  const transport = workflowTransport(tenant);
  const [prompt, setPrompt] = useState("");
  const [opening, setOpening] = useState("");
  const [openings, setOpenings] = useState<Opening[]>([]);
  const [recents, setRecents] = useState<Recent[]>([]);
  const [saved, setSaved] = useState<Recent[]>([]);
  const [panel, setPanel] = useState(false);
  const [loading, setLoading] = useState(true);
  const [sidebarError, setSidebarError] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const completedSearch = useRef<string | null>(null);
  const executionRetry = useRef(crypto.randomUUID());
  const [speechStatus, setSpeechStatus] = useState("Typed search is ready.");
  const [speechAvailable, setSpeechAvailable] = useState(false);
  const [listening, setListening] = useState(false);
  const recognition = useRef<Recognition | null>(null);
  const panelToggle = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLDialogElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (panel) sidebar.current?.showModal();
  }, [panel]);
  const refresh = async () => {
    setLoading(true);
    setSidebarError(false);
    try {
      const responses = await Promise.all(
        ["openings", "recent-searches", "saved-searches"].map((path) =>
          request(`${base}/${path}`),
        ),
      );
      if (responses.some((response) => !response.ok))
        throw new Error("Unavailable");
      const [projects, recent, named] = await Promise.all(
        responses.map((response) => response.json()),
      );
      setOpenings(projects);
      setRecents(recent);
      setSaved(named);
    } catch {
      setSidebarError(true);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void refresh();
  }, []); // trusted page context is immutable per mount
  useEffect(() => {
    const browser = window as unknown as {
      SpeechRecognition?: new () => Recognition;
      webkitSpeechRecognition?: new () => Recognition;
    };
    const Constructor =
      browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
    if (!Constructor) {
      setSpeechStatus(
        "Speech input is unavailable. Typed search remains fully usable.",
      );
      return;
    }
    const engine = new Constructor();
    recognition.current = engine;
    engine.continuous = false;
    engine.interimResults = true;
    engine.lang = "en-IN";
    engine.onstart = () => {
      setListening(true);
      setSpeechStatus("Listening…");
    };
    engine.onresult = (event) => {
      setPrompt(
        Array.from(event.results)
          .map((r) => r[0].transcript)
          .join(""),
      );
      setSpeechStatus("Transcript ready. Edit it, then choose Search.");
    };
    engine.onerror = () => {
      setListening(false);
      setSpeechStatus("Speech is unavailable. Continue by typing.");
    };
    engine.onend = () => setListening(false);
    setSpeechAvailable(true);
    return () => {
      engine.onresult = null;
      engine.onend = null;
      engine.onerror = null;
      engine.stop();
      recognition.current = null;
    };
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || uncertain) return;
    if (!prompt.trim()) {
      setError("Describe the role before searching.");
      composer.current?.focus();
      return;
    }
    setBusy(true);
    setError("");
    setStatus("Interpreting the hiring need…");
    let executing = false;
    try {
      if (completedSearch.current) {
        transport.navigate(
          "search-results",
          await transport.create(
            "search-results",
            { search_id: completedSearch.current },
            executionRetry.current,
          ),
        );
        return;
      }
      const response = await request(`${base}/searches/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt.trim(),
          context: opening
            ? { type: "OPENING", opening_id: opening }
            : { type: "AD_HOC" },
        }),
      });
      if (!response.ok)
        throw new Error(
          response.status === 429
            ? "Too many requests. Wait before trying again."
            : "Interpretation is unavailable. Your typed query remains here.",
        );
      const intent = (await response.json()) as {
        criteria: { groups?: unknown[]; criteria?: unknown[] };
        requires_review: boolean;
        ai_status: string;
        ambiguities: string[];
      };
      if (
        intent.requires_review !== false ||
        !["USED", "NOT_NEEDED"].includes(intent.ai_status) ||
        !Array.isArray(intent.ambiguities) ||
        intent.ambiguities.length ||
        !intent.criteria ||
        typeof intent.criteria !== "object" ||
        !Array.isArray(intent.criteria.groups) ||
        !Array.isArray(intent.criteria.criteria) ||
        !intent.criteria.criteria.length
      ) {
        throw new Error(
          "Clarify your query before searching. Interpretation is ambiguous, unsafe or could not be validated. No search ran; edit the query and try again.",
        );
      }
      setStatus("Searching authorized candidates…");
      executing = true;
      const result = await request(`${base}/searches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(intent.criteria),
      });
      if (!result.ok) {
        if (result.status < 500) executing = false;
        throw new Error(
          "Search is unavailable. Your typed query remains here.",
        );
      }
      const data = (await result.json()) as { search_id: string };
      if (
        typeof data.search_id !== "string" ||
        !/^[a-f0-9-]{36}$/i.test(data.search_id)
      )
        throw new Error("Search outcome unavailable");
      completedSearch.current = data.search_id;
      executing = false;
      transport.navigate(
        "search-results",
        await transport.create(
          "search-results",
          {
            search_id: data.search_id,
          },
          executionRetry.current,
        ),
      );
    } catch (failure) {
      if (executing) setUncertain(true);
      setError(
        executing
          ? "The search outcome is uncertain. It will not be retried automatically. Reload to start a new search."
          : completedSearch.current
            ? "Search completed, but results could not open. Choose Search to retry opening results without executing again."
            : failure instanceof Error
              ? failure.message
              : "Search is unavailable.",
      );
      setStatus("");
      setBusy(false);
    }
  };
  const reopen = async (searchId: string, named: boolean) => {
    setBusy(true);
    setError("");
    setStatus("Restoring authorized criteria…");
    try {
      const response = await request(
        `${base}/${named ? "saved-searches" : "recent-searches"}/${searchId}`,
      );
      if (!response.ok)
        throw new Error("Search expired or is no longer available.");
      transport.navigate(
        "search-results",
        await transport.create("search-results", { search_id: searchId }),
      );
    } catch {
      setError("Search expired or is no longer available. Start a new search.");
      setBusy(false);
      setStatus("");
    }
  };
  const closePanel = () => {
    sidebar.current?.close();
    setPanel(false);
    panelToggle.current?.focus();
  };
  return (
    <div className="ui-search-home">
      <SkipLink />
      <Header>
        <span>Recruiter workspace</span>
        <Button
          variant="secondary"
          onClick={async () => {
            setBusy(true);
            try {
              const response = await request("/api/v1/session/sign-out", {
                method: "DELETE",
              });
              if (response.ok) {
                setPrompt("");
                setRecents([]);
                setSaved([]);
                location.replace("/api/v1/auth/login");
              } else {
                setError("Sign-out failed. Try again.");
                setBusy(false);
              }
            } catch {
              setError("Sign-out failed. Try again.");
              setBusy(false);
            }
          }}
        >
          Sign out
        </Button>
      </Header>
      <div className="ui-search-tools">
        <Button
          variant="secondary"
          onClick={() => {
            setPrompt("");
            setOpening("");
            composer.current?.focus();
          }}
        >
          New search
        </Button>
        <Button
          ref={panelToggle}
          variant="secondary"
          aria-expanded={panel}
          aria-controls="search-sidebar"
          onClick={() => setPanel(!panel)}
        >
          Projects and recents
        </Button>
      </div>
      <main id="main" tabIndex={-1} className="ui-search-stage">
        <h1>Who are we hiring today?</h1>
        <form className="ui-search-composer" onSubmit={submit}>
          <label className="ui-visually-hidden" htmlFor="hiring-prompt">
            Describe the candidate you need
          </label>
          <textarea
            id="hiring-prompt"
            ref={composer}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={4000}
            placeholder="Example: Backend engineers in Bengaluru, 4–7 years, Java, Kafka"
            aria-describedby="search-feedback"
          />
          <div className="ui-composer-bottom">
            <label>
              Search context
              <select
                value={opening}
                onChange={(event) => setOpening(event.target.value)}
              >
                <option value="">Ad-hoc search</option>
                {openings
                  .filter((item) => item.state === "OPEN")
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title}
                    </option>
                  ))}
              </select>
            </label>
            <Button
              type="button"
              variant="secondary"
              disabled={!speechAvailable || busy}
              aria-pressed={listening}
              onClick={() => {
                try {
                  if (listening) recognition.current?.stop();
                  else recognition.current?.start();
                } catch {
                  setSpeechStatus("Speech is unavailable. Continue by typing.");
                }
              }}
            >
              Use speech
            </Button>
            <Button type="submit" busy={busy} disabled={busy || uncertain}>
              Search
            </Button>
          </div>
        </form>
        <StatusMessage>{speechStatus}</StatusMessage>
        <div id="search-feedback">
          <StatusMessage>{status}</StatusMessage>
          {error && <Alert>{error}</Alert>}
        </div>
        <nav className="ui-suggested" aria-label="Suggested searches">
          {[
            "0-to-1 backend builders",
            "Production ML engineers",
            "Founding engineers",
          ].map((text) => (
            <Button
              key={text}
              variant="secondary"
              onClick={() => {
                setPrompt(text);
                composer.current?.focus();
              }}
            >
              {text}
            </Button>
          ))}
        </nav>
      </main>
      {panel && (
        <dialog
          ref={sidebar}
          id="search-sidebar"
          className="ui-search-sidebar"
          aria-label="Projects and recents"
          onCancel={(event) => {
            event.preventDefault();
            closePanel();
          }}
        >
          <Button variant="secondary" onClick={closePanel}>
            Close panel
          </Button>
          {loading ? (
            <StatusMessage>Loading authorized searches…</StatusMessage>
          ) : sidebarError ? (
            <>
              <Alert>Projects and searches are unavailable.</Alert>
              <Button onClick={() => void refresh()}>Retry</Button>
            </>
          ) : (
            <>
              <details>
                <summary>Projects</summary>
                {openings.length ? (
                  openings.map((item) => (
                    <Button
                      key={item.id}
                      disabled={item.state !== "OPEN"}
                      variant="secondary"
                      onClick={() => {
                        setOpening(item.id);
                        closePanel();
                        composer.current?.focus();
                      }}
                    >
                      {item.title}
                    </Button>
                  ))
                ) : (
                  <p>No authorized openings.</p>
                )}
              </details>
              <details open>
                <summary>Recents</summary>
                {recents.length ? (
                  recents.map((item, index) => (
                    <Button
                      key={item.search_id}
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void reopen(item.search_id, false)}
                    >
                      Recent search {index + 1}
                    </Button>
                  ))
                ) : (
                  <p>No recent searches. Start with the composer.</p>
                )}
              </details>
              <details>
                <summary>Saved searches</summary>
                {saved.length ? (
                  saved.map((item) => (
                    <Button
                      key={item.search_id}
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void reopen(item.search_id, true)}
                    >
                      {item.name}
                    </Button>
                  ))
                ) : (
                  <p>No saved searches.</p>
                )}
              </details>
            </>
          )}
        </dialog>
      )}
    </div>
  );
}
