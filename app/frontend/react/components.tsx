import {
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type ComponentProps,
} from "react";
import type { ConflictPayload } from "../shared/conflict-resolution";

const enterLogo = new URL("./assets/enter-logo.jpeg", import.meta.url).href;

type Children = { children: ReactNode };
export function VisuallyHidden({ children }: Children) {
  return <span className="ui-visually-hidden">{children}</span>;
}
export function SkipLink({ target = "main" }: { target?: string }) {
  return (
    <a className="ui-skip" href={`#${target}`}>
      Skip to main content
    </a>
  );
}
export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <a href={href} className="ui-wordmark" aria-label="enter home">
      <span className="ui-logo-frame">
        <img src={enterLogo} alt="enter" />
      </span>
    </a>
  );
}
export function Header({ children }: { children?: ReactNode }) {
  return (
    <header className="ui-header">
      <Wordmark />
      {children}
    </header>
  );
}
export function PlatformNavigation({
  active,
  tenantId,
}: {
  active: "search" | "results" | "candidate";
  tenantId?: string;
}) {
  const search = tenantId
    ? `/tenants/${tenantId}/recruiter/search/`
    : "/api/v1/auth/login";
  return (
    <>
      <span className="platform-brand-label">Talent Platform</span>
      <nav className="platform-navigation" aria-label="Platform">
        <a
          href={search}
          aria-current={active === "search" ? "page" : undefined}
        >
          Search
        </a>
        <a
          href={`${search}?view=results`}
          aria-current={active === "results" ? "page" : undefined}
        >
          Results
        </a>
        <a
          href={
            active === "candidate"
              ? "/candidate/profile/"
              : "/api/v1/auth/login?platform=candidate"
          }
          aria-current={active === "candidate" ? "page" : undefined}
        >
          Candidate Platform
        </a>
      </nav>
      <a className="platform-privacy-link" href="/candidate/rights/">
        Privacy
      </a>
    </>
  );
}
export function WorkspaceNavigation({
  label,
  items,
}: {
  label: string;
  items: { label: string; href: string; current?: boolean }[];
}) {
  return (
    <nav className="ui-nav" aria-label={label}>
      {items.map((item) => (
        <a
          key={item.href}
          href={item.href}
          aria-current={item.current ? "page" : undefined}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}
export function Container({
  children,
  width = "search",
}: Children & { width?: "search" | "profile" | "public" }) {
  return (
    <div className="ui-container" data-width={width}>
      {children}
    </div>
  );
}
export function ResponsiveGrid({ children }: Children) {
  return <div className="ui-grid">{children}</div>;
}
export function AppShell({
  children,
  navigation,
  title,
}: Children & { navigation?: ReactNode; title: string }) {
  return (
    <div className="ui-shell">
      <SkipLink />
      <Header>{navigation}</Header>
      <main id="main" tabIndex={-1}>
        <Container>
          <div className="ui-stack">
            <h1>{title}</h1>
            {children}
          </div>
        </Container>
      </main>
    </div>
  );
}
export function Button({
  variant = "primary",
  busy = false,
  children,
  ...props
}: ComponentProps<"button"> & {
  variant?: "primary" | "secondary" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      type="button"
      {...props}
      className={`ui-button ${props.className ?? ""}`}
      data-variant={variant}
      disabled={props.disabled || busy}
      aria-busy={busy || undefined}
    >
      {children}
    </button>
  );
}
export function IconButton({
  label,
  children,
  ...props
}: Omit<ComponentProps<typeof Button>, "aria-label"> & { label: string }) {
  return (
    <Button {...props} className="ui-icon-button" aria-label={label}>
      <span aria-hidden="true">{children}</span>
    </Button>
  );
}
export function TextInput(props: ComponentProps<"input">) {
  return <input {...props} className="ui-control" />;
}
export function Textarea(props: ComponentProps<"textarea">) {
  return <textarea {...props} className="ui-control" />;
}
export function Select(props: ComponentProps<"select">) {
  return <select {...props} className="ui-control" />;
}
export function Checkbox({
  label,
  ...props
}: Omit<ComponentProps<"input">, "type"> & { label: string }) {
  return (
    <label className="ui-choice">
      <input {...props} type="checkbox" />
      {label}
    </label>
  );
}
export function Radio({
  label,
  ...props
}: Omit<ComponentProps<"input">, "type"> & { label: string }) {
  return (
    <label className="ui-choice">
      <input {...props} type="radio" />
      {label}
    </label>
  );
}
type FieldControl = {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
};
export function Field({
  label,
  help,
  error,
  children,
}: {
  label: string;
  help?: string;
  error?: string;
  children: (props: FieldControl) => ReactNode;
}) {
  const id = useId();
  const descriptions = [help ? `${id}-help` : "", error ? `${id}-error` : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="ui-field">
      <label htmlFor={id}>{label}</label>
      {children({
        id,
        "aria-describedby": descriptions || undefined,
        "aria-invalid": error ? true : undefined,
      })}
      {help && (
        <p id={`${id}-help`} className="ui-help">
          {help}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="ui-validation" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
export function Card({
  children,
  title,
  className,
  ...props
}: Children & { title?: string } & ComponentProps<"section">) {
  return (
    <section {...props} className={`ui-card ${className ?? ""}`}>
      {title && <h2>{title}</h2>}
      {children}
    </section>
  );
}
export type Tone = "sage" | "gold" | "clay" | "unknown";
export function Chip({ children, tone }: Children & { tone?: Tone }) {
  return (
    <span className="ui-chip" data-tone={tone}>
      {children}
    </span>
  );
}
export const Badge = Chip;
export function Alert({ children, tone = "clay" }: Children & { tone?: Tone }) {
  return (
    <div className="ui-alert" data-tone={tone} role="alert">
      {children}
    </div>
  );
}
export function StatusMessage({ children }: Children) {
  return (
    <p
      className="ui-status"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      {children}
    </p>
  );
}
export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="ui-stack">
      <StatusMessage>{label}</StatusMessage>
      <div aria-hidden="true" className="ui-skeleton" />
      <div aria-hidden="true" className="ui-skeleton" />
    </div>
  );
}
export function EmptyState({
  title,
  children,
  action,
  illustration,
}: Children & {
  title: string;
  action?: ReactNode;
  illustration?: { src: string; width: number; height: number };
}) {
  return (
    <Card
      className="ui-empty-state"
      data-has-illustration={illustration ? "true" : undefined}
    >
      {illustration && (
        <img
          className="ui-empty-illustration"
          src={illustration.src}
          width={illustration.width}
          height={illustration.height}
          alt=""
          aria-hidden="true"
          loading="lazy"
          decoding="async"
        />
      )}
      <div className="ui-empty-state-body">
        <h2>{title}</h2>
        <div className="ui-empty-state-copy">{children}</div>
        {action}
      </div>
    </Card>
  );
}
export function DegradedState({ children }: Children) {
  return <Alert tone="gold">{children}</Alert>;
}
export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="ui-stack">
      <Alert>Unable to load current information. No saved copy is shown.</Alert>
      <Button variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
export function Dialog({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    if (!open) return;
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    dialog.showModal();
    close.current?.focus();
    return () => {
      dialog.close();
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="ui-dialog"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const nodes = Array.from(
          ref.current!.querySelectorAll<HTMLElement>(
            'button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]',
          ),
        ).filter((el) => el.getClientRects().length > 0);
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
    >
      <div className="ui-stack">
        <div className="ui-row">
          <h2 id={titleId}>{title}</h2>
          <button
            className="ui-button"
            type="button"
            ref={close}
            onClick={onClose}
          >
            Close dialog
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
export function ConflictPanel({
  conflict,
  onDiscard,
  onReview,
  onResubmit,
}: {
  conflict: ConflictPayload;
  onDiscard: () => void;
  onReview: () => void;
  onResubmit: () => void;
}) {
  const region = useRef<HTMLDivElement>(null);
  useEffect(() => {
    region.current?.focus();
  }, [conflict]);
  return (
    <div
      className="ui-stack"
      ref={region}
      tabIndex={-1}
      role="region"
      aria-label="Resolve changed information"
    >
      <Alert tone="gold">
        A newer version is available. Nothing was overwritten.
      </Alert>
      <dl>
        {conflict.changed_fields.map((field) => (
          <div key={field}>
            <dt>{field.replaceAll("_", " ")}</dt>
            <dd>
              Stored: {String(conflict.current[field] ?? "Unknown")}; attempted:{" "}
              {String(conflict.attempted[field] ?? "Unknown")}
            </dd>
          </div>
        ))}
      </dl>
      <div className="ui-row">
        <Button onClick={onDiscard}>Use stored version</Button>
        <Button variant="secondary" onClick={onReview}>
          Review and merge
        </Button>
        <Button variant="secondary" onClick={onResubmit}>
          Resubmit reviewed changes
        </Button>
      </div>
    </div>
  );
}
export function Table({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: string[];
  rows: ReactNode[][];
}) {
  return (
    <div
      className="ui-table-wrap"
      role="region"
      aria-label={caption}
      tabIndex={0}
    >
      <table>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th scope="col" key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function List({ children }: Children) {
  return <ul className="ui-list">{children}</ul>;
}
