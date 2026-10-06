import {
  LoaderCircle,
  Mic,
  Send,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  forwardRef,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEventHandler,
  type KeyboardEvent,
} from "react";

type SearchSuggestion = {
  label: string;
  icon?: LucideIcon;
};

interface AnimatedAIChatProps {
  value: string;
  onValueChange: (value: string) => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onSpeechToggle: () => void;
  onSuggestion: (value: string) => void;
  suggestions: SearchSuggestion[];
  speechAvailable: boolean;
  listening: boolean;
  busy: boolean;
  disabled?: boolean;
  describedBy?: string;
}

function useAutoResizeTextarea(value: string) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "64px";
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 64), 176)}px`;
  }, []);

  useEffect(() => adjustHeight(), [adjustHeight, value]);
  useEffect(() => {
    window.addEventListener("resize", adjustHeight);
    return () => window.removeEventListener("resize", adjustHeight);
  }, [adjustHeight]);

  return { textareaRef, adjustHeight };
}

export const AnimatedAIChat = forwardRef<
  HTMLTextAreaElement,
  AnimatedAIChatProps
>(function AnimatedAIChat(
  {
    value,
    onValueChange,
    onSubmit,
    onSpeechToggle,
    onSuggestion,
    suggestions,
    speechAvailable,
    listening,
    busy,
    disabled = false,
    describedBy,
  },
  forwardedRef,
) {
  const [focused, setFocused] = useState(false);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea(value);
  const formRef = useRef<HTMLFormElement>(null);
  const reducedMotion = useReducedMotion();
  const unavailable = busy || disabled;

  const assignTextarea = (node: HTMLTextAreaElement | null) => {
    textareaRef.current = node;
    if (typeof forwardedRef === "function") forwardedRef(node);
    else if (forwardedRef) forwardedRef.current = node;
  };

  const changeValue = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onValueChange(event.target.value);
    adjustHeight();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  };

  return (
    <div className="animated-talent-search fm:relative fm:w-full fm:overflow-hidden">
      <div className="animated-talent-search__glow" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>

      <motion.div
        className="animated-talent-search__content fm:relative fm:z-10 fm:mx-auto fm:w-full fm:max-w-2xl"
        initial={reducedMotion ? false : { opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
      >
        <div className="animated-talent-search__intro fm:text-center">
          <div className="animated-talent-search__eyebrow">
            <Sparkles size={15} aria-hidden="true" />
            Natural-language talent search
          </div>
          <h1>Who are we hiring today?</h1>
          <p>
            Describe the role, experience, skills, location and availability.
          </p>
        </div>

        <motion.form
          ref={formRef}
          className="animated-talent-search__composer fm:relative fm:overflow-hidden fm:rounded-2xl"
          onSubmit={onSubmit}
          initial={reducedMotion ? false : { scale: 0.985 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.3 }}
        >
          <label className="ui-visually-hidden" htmlFor="hiring-prompt">
            Describe the candidate you need
          </label>
          <textarea
            id="hiring-prompt"
            ref={assignTextarea}
            value={value}
            onChange={changeValue}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            disabled={unavailable}
            maxLength={4000}
            rows={2}
            placeholder="Example: Backend engineer in Bengaluru, 5–8 years, Python, FastAPI, available within 30 days"
            aria-describedby={describedBy}
          />

          <AnimatePresence>
            {focused && (
              <motion.span
                className="animated-talent-search__focus"
                aria-hidden="true"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reducedMotion ? 0 : 0.18 }}
              />
            )}
          </AnimatePresence>

          <div className="animated-talent-search__actions fm:flex fm:items-center fm:justify-between fm:gap-3">
            <button
              type="button"
              className="animated-talent-search__icon-button"
              aria-label="Use speech"
              title={
                speechAvailable
                  ? "Use speech"
                  : "Speech input is unavailable in this browser"
              }
              disabled={!speechAvailable || unavailable}
              aria-pressed={listening}
              onClick={onSpeechToggle}
            >
              <Mic size={18} aria-hidden="true" />
            </button>

            <button
              type="submit"
              className="animated-talent-search__submit fm:flex fm:items-center fm:gap-2"
              aria-label="Search"
              aria-busy={busy || undefined}
              disabled={unavailable}
            >
              {busy ? (
                <LoaderCircle
                  className="animated-talent-search__spinner"
                  size={17}
                  aria-hidden="true"
                />
              ) : (
                <Send size={17} aria-hidden="true" />
              )}
              <span>{busy ? "Searching" : "Search"}</span>
            </button>
          </div>
        </motion.form>

        <nav
          className="animated-talent-search__suggestions fm:flex fm:flex-wrap fm:items-center fm:justify-center fm:gap-2"
          aria-label="Suggested searches"
        >
          {suggestions.map(({ label, icon: Icon = Sparkles }, index) => (
            <motion.button
              key={label}
              type="button"
              disabled={unavailable}
              onClick={() => {
                onSuggestion(label);
                textareaRef.current?.focus();
              }}
              initial={reducedMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: reducedMotion ? 0 : index * 0.06 }}
            >
              <Icon size={14} aria-hidden="true" />
              <span>{label}</span>
            </motion.button>
          ))}
        </nav>
      </motion.div>
    </div>
  );
});
