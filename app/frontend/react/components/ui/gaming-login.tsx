import {
  ArrowRight,
  BriefcaseBusiness,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import type { MouseEvent, ReactNode } from "react";

interface LoginFormProps {
  entryError?: boolean;
  onNavigate?: (message: string) => void;
}

interface VideoBackgroundProps {
  videoUrl?: string;
}

interface AccessOptionProps {
  href: string;
  icon: ReactNode;
  title: string;
  detail: string;
  primary?: boolean;
  onNavigate: (event: MouseEvent<HTMLAnchorElement>) => void;
}

function AccessOption({
  href,
  icon,
  title,
  detail,
  primary = false,
  onNavigate,
}: AccessOptionProps) {
  return (
    <a
      href={href}
      className="enter-access-option"
      data-primary={primary || undefined}
      onClick={onNavigate}
    >
      <span className="enter-access-option__icon" aria-hidden="true">
        {icon}
      </span>
      <span className="enter-access-option__copy">
        <strong>{title}</strong>
        <span>{detail}</span>
      </span>
      <ArrowRight
        className="enter-access-option__arrow"
        size={19}
        aria-hidden="true"
      />
    </a>
  );
}

function VideoBackground({ videoUrl }: VideoBackgroundProps) {
  return (
    <div className="enter-access-background" aria-hidden="true">
      {videoUrl ? (
        <video autoPlay loop muted playsInline preload="metadata">
          <source src={videoUrl} type="video/mp4" />
        </video>
      ) : null}
      <div className="enter-access-background__veil" />
      <div className="enter-access-background__orb enter-access-background__orb--one" />
      <div className="enter-access-background__orb enter-access-background__orb--two" />
      <div className="enter-access-background__orb enter-access-background__orb--three" />
      <div className="enter-access-background__grid" />
    </div>
  );
}

function LoginForm({ entryError, onNavigate }: LoginFormProps) {
  const announce = (event: MouseEvent<HTMLAnchorElement>, message: string) => {
    if (
      event.button === 0 &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      !event.altKey
    ) {
      onNavigate?.(message);
    }
  };

  return (
    <section className="enter-access-card" aria-labelledby="login-title">
      <header className="enter-access-brand">
        <a href="/" className="enter-access-logo" aria-label="enter home">
          enter
        </a>
        <span>Talent Platform</span>
      </header>

      <div className="enter-access-intro">
        <div className="enter-access-kicker">
          <Sparkles size={14} aria-hidden="true" />
          Connected hiring
        </div>
        <h1 id="login-title">Welcome to Enter</h1>
        <p>
          Discover exceptional talent or shape the profile that gets you
          discovered.
        </p>
      </div>

      {entryError ? (
        <div className="enter-access-error" role="alert">
          Sign-in could not be completed. Try secure sign-in again.
        </div>
      ) : null}

      <div className="enter-access-divider">
        <span>Choose your workspace</span>
      </div>

      <nav className="enter-access-options" aria-label="Sign-in options">
        <AccessOption
          href="/api/v1/auth/login"
          icon={<BriefcaseBusiness size={20} />}
          title="Recruiter sign-in"
          detail="Search, review and manage talent"
          primary
          onNavigate={(event) =>
            announce(event, "Opening secure recruiter sign-in…")
          }
        />
        <AccessOption
          href="/candidate/profile/"
          icon={<User size={20} />}
          title="Candidate platform"
          detail="Upload your resume and shape your profile"
          onNavigate={(event) =>
            announce(event, "Opening your candidate profile…")
          }
        />
      </nav>

      <div className="enter-access-security">
        <ShieldCheck size={18} aria-hidden="true" />
        <p>
          Authentication and workspace access are verified securely by the
          server. Enter never collects your password on this page.
        </p>
      </div>
    </section>
  );
}

const LoginPage = { LoginForm, VideoBackground };

export default LoginPage;
