import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  Button,
  Header,
  SkipLink,
  StatusMessage,
  Alert,
  PlatformNavigation,
  Field,
  TextInput,
  Select,
  Chip,
} from "./components";
import { AnimatedAIChat } from "./components/ui/animated-ai-chat";
import type { PageProps } from "./mount";
import type { Recognition } from "../recruiter/speech-search";
import { workflowTransport } from "../shared/workflow-handoff";

type Opening = { id: string; title: string; state: string };
type Recent = { search_id: string; created_at: string; name?: string };
type Criterion = {
  id: string;
  group_id: string;
  field: string;
  operator: string;
  value: string | number | boolean | string[];
};
type Criteria = {
  context: Record<string, string>;
  groups: {
    id: string;
    purpose: "REQUIREMENT" | "PREFERENCE" | "EXCLUSION";
    operator: "ANY" | "ALL";
    label?: string | null;
  }[];
  criteria: Criterion[];
  limit: number;
};
type Clarification = {
  id: "skills" | "location" | "work_arrangement" | "experience_rule";
  question: string;
  kind: "TEXT" | "CHOICE";
  options: string[];
  allow_any: boolean;
};
type InterpretedSearch = {
  original_prompt: string;
  workflow_id: string;
  criteria: Criteria;
  requires_review: boolean;
  ai_status: string;
  ambiguities: string[];
  clarifications: Clarification[];
  estimated_count?: number;
};
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
  const [review, setReview] = useState<InterpretedSearch | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
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
  const execute = async (criteria: Criteria) => {
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
      setStatus("Searching authorized candidates…");
      executing = true;
      const result = await request(`${base}/searches`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(criteria),
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
    setReview(null);
    setStatus("Interpreting the hiring need…");
    try {
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
      const intent = (await response.json()) as InterpretedSearch;
      intent.ambiguities = Array.isArray(intent.ambiguities)
        ? intent.ambiguities
        : [];
      intent.clarifications = Array.isArray(intent.clarifications)
        ? intent.clarifications
        : [];
      if (
        !intent.criteria ||
        !Array.isArray(intent.criteria.groups) ||
        !Array.isArray(intent.criteria.criteria) ||
        !intent.criteria.criteria.length
      )
        throw new Error(
          "The request could not be converted into safe search criteria. Edit it and try again.",
        );
      const unsafe = intent.ambiguities.some((item) =>
        /protected|instruction-like|unsafe/i.test(item),
      );
      if (unsafe)
        throw new Error(
          "The request contains criteria that cannot be used in hiring. Remove protected or instruction-like terms and try again.",
        );
      if (intent.requires_review || intent.clarifications.length) {
        setReview(intent);
        setAnswers(
          Object.fromEntries(
            intent.clarifications.map((item) => [
              item.id,
              item.id === "experience_rule" ? "AT_LEAST" : "ANY",
            ]),
          ),
        );
        setStatus("I found a few details to confirm before searching.");
        setBusy(false);
        return;
      }
      await execute(intent.criteria);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Interpretation is unavailable.",
      );
      setStatus("");
      setBusy(false);
    }
  };
  const confirmRequirements = async () => {
    if (!review || busy) return;
    setBusy(true);
    setError("");
    setStatus("Confirming the recruiter-reviewed requirements…");
    const criteria: Criteria = JSON.parse(JSON.stringify(review.criteria));
    const addGroup = (operator: "ANY" | "ALL", label: string) => {
      const id = crypto.randomUUID();
      criteria.groups.push({
        id,
        purpose: "REQUIREMENT",
        operator,
        label,
      });
      return id;
    };
    const add = (
      field: string,
      operator: string,
      value: string,
      groupId: string,
    ) =>
      criteria.criteria.push({
        id: crypto.randomUUID(),
        group_id: groupId,
        field,
        operator,
        value,
      });
    const skills = (answers.skills ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item && item !== "ANY");
    if (skills.length) {
      const group = addGroup("ALL", "Essential skills");
      skills.forEach((skill) => add("skill", "CONTAINS", skill, group));
    }
    const locations = (answers.location ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item && item !== "ANY");
    if (locations.length) {
      const group = addGroup("ANY", "Accepted locations");
      locations.forEach((location) => add("location", "EQ", location, group));
    }
    if (answers.work_arrangement && answers.work_arrangement !== "ANY") {
      const group = addGroup("ALL", "Work arrangement");
      add("work_arrangement", "EQ", answers.work_arrangement, group);
    }
    if (answers.experience_rule === "EXACT")
      criteria.criteria = criteria.criteria.map((item) =>
        item.field === "experience_years" ? { ...item, operator: "EQ" } : item,
      );
    try {
      const response = await request(`${base}/searches/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: review.original_prompt,
          context: criteria.context,
          criteria,
          workflow_id: review.workflow_id,
        }),
      });
      if (!response.ok)
        throw new Error(
          "The reviewed requirements could not be confirmed. Check the answers and try again.",
        );
      const { criteria: confirmed } =
        (await response.json()) as InterpretedSearch;
      setReview(null);
      await execute(confirmed);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "The reviewed requirements could not be confirmed.",
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
        <PlatformNavigation active="search" tenantId={tenant} />
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
                location.replace("/");
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
          Logout
        </Button>
      </Header>
      <div className="ui-search-tools">
        <Button
          variant="secondary"
          aria-label="New search"
          title="New search"
          disabled={busy || uncertain}
          onClick={() => {
            setError("");
            setStatus("");
            completedSearch.current = null;
            executionRetry.current = crypto.randomUUID();
            setPrompt("");
            setOpening("");
            setReview(null);
            setAnswers({});
            composer.current?.focus();
          }}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 4v16M4 12h16" />
          </svg>
        </Button>
        <Button
          aria-label="Projects and recents"
          title="Projects and recents"
          ref={panelToggle}
          variant="secondary"
          aria-expanded={panel}
          aria-controls="search-sidebar"
          onClick={() => setPanel(!panel)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="m12 3 8 4-8 4-8-4 8-4Zm-8 9 8 4 8-4M4 17l8 4 8-4" />
          </svg>
        </Button>
      </div>
      <main id="main" tabIndex={-1} className="ui-search-stage">
        <AnimatedAIChat
          ref={composer}
          value={prompt}
          onValueChange={setPrompt}
          onSubmit={submit}
          busy={busy}
          disabled={uncertain}
          speechAvailable={speechAvailable}
          listening={listening}
          describedBy="search-feedback"
          onSpeechToggle={() => {
            try {
              if (listening) recognition.current?.stop();
              else recognition.current?.start();
            } catch {
              setSpeechStatus("Speech is unavailable. Continue by typing.");
            }
          }}
          suggestions={[
            { label: "0→1 backend builders" },
            { label: "Production ML engineers" },
            { label: "Founding engineers" },
          ]}
          onSuggestion={(value) => setPrompt(value)}
        />
        <div
          className={
            speechStatus === "Typed search is ready." ||
            speechStatus.startsWith("Speech input is unavailable.")
              ? "ui-visually-hidden"
              : "ui-search-speech-status"
          }
        >
          <StatusMessage>{speechStatus}</StatusMessage>
        </div>
        <div id="search-feedback">
          <StatusMessage>{status}</StatusMessage>
          {error && <Alert>{error}</Alert>}
        </div>
        {review && (
          <section
            className="search-clarification"
            aria-labelledby="clarification-title"
          >
            <div className="search-clarification__heading">
              <div>
                <span>Human review</span>
                <h2 id="clarification-title">Let’s sharpen the search</h2>
                <p>
                  I translated your request into filters. Confirm the missing
                  details before any candidate search runs.
                </p>
              </div>
              {typeof review.estimated_count === "number" && (
                <strong>{review.estimated_count} currently in scope</strong>
              )}
            </div>
            <div
              className="search-clarification__criteria"
              aria-label="Detected requirements"
            >
              {review.criteria.criteria.map((item) => (
                <Chip key={item.id} tone="sage">
                  {item.field.replaceAll("_", " ")} · {String(item.value)}
                </Chip>
              ))}
            </div>
            <div className="search-clarification__questions">
              {review.clarifications.map((item) => (
                <Field key={item.id} label={item.question}>
                  {(props) =>
                    item.kind === "CHOICE" ? (
                      <Select
                        {...props}
                        value={answers[item.id] ?? "ANY"}
                        disabled={busy}
                        onChange={(event) =>
                          setAnswers((current) => ({
                            ...current,
                            [item.id]: event.target.value,
                          }))
                        }
                      >
                        {item.allow_any && (
                          <option value="ANY">Any / no restriction</option>
                        )}
                        {item.options.map((option) => (
                          <option key={option} value={option}>
                            {option.replaceAll("_", " ").toLowerCase()}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <TextInput
                        {...props}
                        value={
                          answers[item.id] === "ANY"
                            ? ""
                            : (answers[item.id] ?? "")
                        }
                        disabled={busy}
                        placeholder={
                          item.id === "skills"
                            ? "Python, Django, PostgreSQL — or leave blank for any"
                            : "Bengaluru, Mumbai — or leave blank for any"
                        }
                        onChange={(event) =>
                          setAnswers((current) => ({
                            ...current,
                            [item.id]: event.target.value,
                          }))
                        }
                      />
                    )
                  }
                </Field>
              ))}
            </div>
            <footer>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  setReview(null);
                  setStatus("");
                  composer.current?.focus();
                }}
              >
                Edit original request
              </Button>
              <Button busy={busy} onClick={() => void confirmRequirements()}>
                Search with these requirements
              </Button>
            </footer>
          </section>
        )}
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
