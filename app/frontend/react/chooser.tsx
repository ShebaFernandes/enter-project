import { useState, type MouseEvent, type ReactNode } from "react";
import { Alert, Header, SkipLink, StatusMessage } from "./components";
import type { PageProps } from "./mount";

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="ui-public-shell">
      <SkipLink />
      <main id="main" tabIndex={-1} className="ui-chooser-stage">
        {children}
      </main>
    </div>
  );
}

export function PlatformChooser({ bootstrap }: PageProps) {
  const [leaving, setLeaving] = useState("");
  const announce = (event: MouseEvent<HTMLAnchorElement>, message: string) => {
    if (
      event.button === 0 &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      !event.altKey
    )
      setLeaving(message);
  };
  return (
    <PublicShell>
      <section className="ui-chooser-card" aria-labelledby="platform-title">
        <Header>
          <span>Talent Platform</span>
        </Header>
        <div className="ui-chooser-note">
          Two platforms in one hiring system
        </div>
        <h1 id="platform-title">Choose your kingdom platform</h1>
        <p>
          Recruiters search and contact matching candidates. Candidates manage
          their profile, explore published openings and apply.
        </p>
        <div className="ui-secure-entry">
          <strong>Secure recruiter access</strong>
          <p>
            Continue to company sign-in. Authentication and workspace access are
            verified securely by the server.
          </p>
        </div>
        <nav className="ui-platform-choices" aria-label="Platform choice">
          <a
            className="ui-platform-primary"
            href="/api/v1/auth/login"
            onClick={(event) =>
              announce(event, "Opening secure recruiter sign-in…")
            }
          >
            <strong>Recruiter</strong>
            <span>Search, review and contact candidates.</span>
          </a>
          <a
            href="/jobs/"
            onClick={(event) => announce(event, "Opening published roles…")}
          >
            <strong>Candidate platform</strong>
            <span>Explore open roles and apply.</span>
          </a>
        </nav>
        <div className="ui-entry-feedback">
          {bootstrap.entryError && (
            <Alert>
              Sign-in could not be completed. Try secure sign-in again, or
              explore public roles.
            </Alert>
          )}
          <StatusMessage>{leaving}</StatusMessage>
        </div>
      </section>
    </PublicShell>
  );
}
