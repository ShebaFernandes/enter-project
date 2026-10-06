import { useState, type ReactNode } from "react";
import { SkipLink, StatusMessage } from "./components";
import LoginPage from "./components/ui/gaming-login";
import type { PageProps } from "./mount";

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="ui-public-shell">
      <SkipLink />
      <main id="main" tabIndex={-1} className="ui-chooser-stage">
        <LoginPage.VideoBackground />
        {children}
      </main>
    </div>
  );
}

export function PlatformChooser({ bootstrap }: PageProps) {
  const [leaving, setLeaving] = useState("");
  return (
    <PublicShell>
      <div className="ui-login-content">
        <LoginPage.LoginForm
          entryError={bootstrap.entryError}
          onNavigate={setLeaving}
        />
        <div className="ui-entry-feedback">
          <StatusMessage>{leaving}</StatusMessage>
        </div>
      </div>
    </PublicShell>
  );
}
