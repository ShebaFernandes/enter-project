import type { FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";

const button =
  "inline-flex min-h-11 items-center justify-center rounded-md bg-[#111342] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#292a56] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#276955] disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton =
  "inline-flex min-h-10 items-center justify-center rounded-md border border-[#d7dbd2] bg-white px-4 py-2 text-sm font-semibold text-[#111342] transition hover:border-[#276955] hover:bg-[#f8faf7] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#276955]";
const field =
  "mt-1.5 block min-h-12 w-full rounded-md border border-[#d7dbd2] bg-white px-3.5 py-3 text-sm text-[#111342] shadow-sm outline-none transition placeholder:text-[#818b98] focus:border-[#276955] focus:ring-4 focus:ring-[#276955]/10";
const label = "block text-sm font-medium text-[#34374c]";
const card =
  "rounded-xl border border-[#d7dbd2] bg-white p-5 shadow-[0_1px_2px_rgba(17,24,39,.05),0_8px_24px_rgba(17,24,39,.06)] sm:p-7";

function Wordmark() {
  return (
    <a href="/" className="flex items-center gap-3 text-inherit no-underline">
      <span className="grid size-9 place-items-center rounded-lg bg-[#111342] text-xs font-extrabold tracking-wide text-white">
        EN
      </span>
      <span className="text-xl font-extrabold tracking-tight text-[#111342]">
        enter
      </span>
    </a>
  );
}

function Chrome({
  context,
  signOut = false,
}: {
  context: string;
  signOut?: boolean;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-[#d7dbd2] bg-white/90 backdrop-blur-xl">
      <div className="mx-auto flex min-h-[76px] max-w-[1320px] flex-wrap items-center justify-between gap-4 px-4 sm:px-7">
        <Wordmark />
        <nav
          aria-label="Workspace navigation"
          className="flex items-center gap-2 rounded-full border border-[#d7dbd2] bg-[#f4f5ef] p-1"
        >
          {context === "recruiter" ? (
            <>
              <a
                className="rounded-full bg-[#111342] px-4 py-2 text-xs font-semibold text-white no-underline"
                href="#search-results"
              >
                Search
              </a>
              <a
                className="rounded-full px-4 py-2 text-xs font-semibold text-[#4b5563] no-underline hover:bg-white"
                href="#recent-searches-heading"
              >
                Recent
              </a>
            </>
          ) : (
            <a
              className="rounded-full bg-[#111342] px-4 py-2 text-xs font-semibold text-white no-underline"
              href="/candidate/profile/"
            >
              My profile
            </a>
          )}
        </nav>
        <div className="flex items-center gap-3 text-sm text-[#4b5563]">
          <span className="hidden items-center gap-2 sm:flex">
            <span className="size-2 rounded-full bg-[#276955]" />
            {context === "recruiter" ? "Recruiter workspace" : "Candidate"}
          </span>
          {signOut ? (
            <button type="button" data-sign-out className={secondaryButton}>
              Sign out
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function RecruiterSearch({
  root,
}: {
  root: HTMLElement & { dataset: DOMStringMap & { tenantId?: string } };
}) {
  const submit = (event: FormEvent<HTMLFormElement>) => event.preventDefault();
  return (
    <div
      className="min-h-screen bg-[#f4f5ef] font-sans text-[#111342] antialiased"
      data-recruiter-search
      data-tenant-id={root.dataset.tenantId}
    >
      <Chrome context="recruiter" signOut />
      <main className="mx-auto grid max-w-[1320px] grid-cols-1 gap-8 px-4 py-8 sm:px-7 lg:grid-cols-[minmax(0,1fr)_290px] lg:gap-10 lg:py-11">
        <div className="min-w-0">
          <a
            className="mb-4 inline-flex text-sm font-semibold text-[#276955] underline-offset-4 hover:underline"
            href="#search-results"
          >
            Skip to results
          </a>
          <div className="mb-7">
            <p className="mb-2 text-xs font-bold uppercase tracking-[.16em] text-[#276955]">
              Recruiter workspace
            </p>
            <h1 className="font-serif text-4xl font-semibold tracking-tight text-[#111342] sm:text-5xl">
              Find your next great hire.
            </h1>
            <p className="mt-3 max-w-2xl text-base leading-7 text-[#4b5563]">
              Describe the role. Review the criteria. Make every shortlist
              decision with evidence.
            </p>
          </div>
          <form
            className="search-form grid gap-5 rounded-2xl border border-[#d7dbd2] bg-white p-5 shadow-[0_16px_42px_rgba(17,24,39,.07)] sm:p-7"
            data-search-form
            onSubmit={submit}
          >
            <input
              type="hidden"
              name="csrfmiddlewaretoken"
              value={root.dataset.csrf ?? ""}
            />
            <div>
              <label className={label} htmlFor="search-prompt">
                What does this person need to do?
              </label>
              <div className="prompt-row mt-2 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
                <textarea
                  className={`${field} min-h-32 resize-y leading-6`}
                  id="search-prompt"
                  name="prompt"
                  maxLength={4000}
                  placeholder="For example: Backend engineer in Bengaluru, 4–7 years, Java and event driven systems…"
                  required
                />
                <button
                  className={secondaryButton}
                  type="button"
                  data-speech
                  aria-pressed="false"
                >
                  Use speech
                </button>
                <button
                  className={`${button} self-start sm:mt-1.5`}
                  type="submit"
                >
                  Search candidates
                </button>
              </div>
              <p
                className="mt-2 min-h-6 text-sm text-[#4b5563]"
                data-speech-status
                role="status"
                aria-live="polite"
              >
                Typed search is ready.
              </p>
            </div>
            <label className={label}>
              Search context
              <select className={field} name="context">
                <option value="AD_HOC">Ad-hoc search</option>
                <option value="OPENING">Active opening</option>
              </select>
            </label>
            <label className={label} data-opening-row hidden>
              Active opening ID
              <input
                className={field}
                name="opening_id"
                inputMode="text"
                autoComplete="off"
              />
            </label>
            <div className="rounded-xl border border-[#d7dbd2] bg-[#fafbf8] p-4 sm:p-5">
              <button
                className="flex w-full items-center justify-between gap-3 text-left text-base font-bold text-[#111342]"
                type="button"
                aria-expanded="true"
                aria-controls="criteria-panel"
                data-toggle-criteria
              >
                Search criteria <span aria-hidden="true">−</span>
              </button>
              <aside
                id="criteria-panel"
                className="criteria-panel mt-4 border-t border-[#d7dbd2] pt-4"
                data-criteria-panel
              >
                <h2 className="text-sm font-semibold text-[#111342]">
                  Deterministic criteria
                </h2>
                <p className="mt-1 text-sm leading-6 text-[#4b5563]">
                  Requirements determine eligibility. Preferences can affect
                  ordering. Protected attributes are never used.
                </p>
                <div className="mt-4 grid gap-3" data-criteria-list />
                <button
                  className={`${secondaryButton} mt-4`}
                  type="button"
                  data-add-criterion
                >
                  + Add criterion
                </button>
              </aside>
            </div>
          </form>
          <p
            className="search-status my-5 min-h-6 text-sm font-medium text-[#276955]"
            role="status"
            aria-live="polite"
          />
          <nav
            className="mb-5 flex flex-wrap gap-2"
            aria-label="Result filters"
          >
            <button
              className={secondaryButton}
              type="button"
              data-filter="all"
              aria-pressed="true"
            >
              All results
            </button>
            <button
              className={secondaryButton}
              type="button"
              data-filter="with-findings"
              aria-pressed="false"
            >
              With informational findings
            </button>
          </nav>
          <section className={card} aria-labelledby="recent-searches-heading">
            <h2
              className="text-xl font-semibold text-[#111342]"
              id="recent-searches-heading"
            >
              Recent searches
            </h2>
            <p className="mt-1 text-sm text-[#4b5563]">
              Your six most recent ad-hoc searches remain available for seven
              days.
            </p>
          </section>
          <section
            className="mt-6 scroll-mt-28"
            id="search-results"
            tabIndex={-1}
            aria-labelledby="results-heading"
          >
            <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[.15em] text-[#276955]">
                  Authorized results
                </p>
                <h2
                  className="mt-1 font-serif text-3xl font-semibold"
                  id="results-heading"
                >
                  Candidates
                </h2>
              </div>
              <div
                className="comparison-toolbar flex flex-wrap items-center gap-3 rounded-xl border border-[#d7dbd2] bg-white p-3"
                data-comparison-toolbar
              >
                <p
                  className="m-0 text-sm text-[#4b5563]"
                  data-comparison-count
                  role="status"
                  aria-live="polite"
                >
                  0 candidates selected for comparison.
                </p>
                <button
                  className={secondaryButton}
                  type="button"
                  data-open-comparison
                  aria-disabled="true"
                >
                  Compare selected
                </button>
              </div>
            </div>
            <div className="grid gap-4" data-results>
              <p className="rounded-xl border border-dashed border-[#b9c2b7] bg-white p-7 text-sm text-[#4b5563]">
                Run a search to see authorized candidates.
              </p>
            </div>
            <button
              className={`${secondaryButton} mt-4`}
              type="button"
              data-more
              hidden
            >
              Load more candidates
            </button>
          </section>
        </div>
        <aside className="space-y-5 lg:sticky lg:top-28 lg:self-start">
          <section className={`${card} border-[#e3d7bd] bg-[#fcf8ef]`}>
            <p className="text-xs font-bold uppercase tracking-[.14em] text-[#a76f15]">
              Hiring, thoughtfully
            </p>
            <h2 className="mt-3 font-serif text-2xl font-semibold leading-tight">
              A clearer view of every candidate.
            </h2>
            <p className="mt-3 text-sm leading-6 text-[#4b5563]">
              See the evidence behind a match. Unknown details stay unknown;
              people make the hiring decisions.
            </p>
          </section>
          <section className={card}>
            <h2 className="text-base font-semibold">A simple workflow</h2>
            <ol className="mt-4 space-y-4 text-sm">
              {[
                ["01", "Describe", "Start with the role and its needs."],
                ["02", "Review", "Confirm criteria before searching."],
                ["03", "Compare", "Use evidence, not automated judgment."],
              ].map(([number, title, detail]) => (
                <li className="flex gap-3" key={number}>
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-[#DDEDE6] text-xs font-bold text-[#276955]">
                    {number}
                  </span>
                  <span>
                    <strong className="block font-semibold">{title}</strong>
                    <span className="mt-0.5 block leading-5 text-[#4b5563]">
                      {detail}
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </main>
      <dialog
        className="max-h-[90vh] overflow-auto rounded-xl border border-[#d7dbd2] p-0 shadow-2xl backdrop:bg-[#111342]/40"
        data-candidate-dialog
        aria-labelledby="candidate-title"
      >
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <h2
              className="font-serif text-2xl font-semibold"
              id="candidate-title"
            >
              Candidate details
            </h2>
            <button className={secondaryButton} type="button" data-close-detail>
              Close
            </button>
          </div>
          <div className="mt-5" data-detail />
        </div>
      </dialog>
    </div>
  );
}

function CandidateProfile() {
  return (
    <div
      className="min-h-screen bg-[#f4f5ef] font-sans text-[#111342] antialiased"
      data-candidate-profile
    >
      <Chrome context="candidate" />
      <main className="mx-auto max-w-[1120px] px-4 py-8 sm:px-7 sm:py-12">
        <header className="mb-7 flex flex-wrap items-end justify-between gap-5">
          <div className="max-w-2xl">
            <p className="mb-2 text-xs font-bold uppercase tracking-[.16em] text-[#276955]">
              Your profile · your choice
            </p>
            <h1 className="font-serif text-4xl font-semibold tracking-tight sm:text-5xl">
              A profile that sounds like you.
            </h1>
            <p className="mt-3 text-base leading-7 text-[#4b5563]">
              Review every detail before publishing. You decide which recruiters
              can discover your profile.
            </p>
          </div>
          <a
            className={`${secondaryButton} no-underline`}
            href="/candidate/rights/"
          >
            Privacy rights centre
          </a>
        </header>
        <div
          className="error-summary mb-4 rounded-xl border-2 border-[#a13e2d] bg-[#fff8f6] p-4 text-sm text-[#a13e2d]"
          role="alert"
          tabIndex={-1}
          hidden
        />
        <div
          className="status mb-4 min-h-6 text-sm font-semibold text-[#276955]"
          role="status"
          aria-live="polite"
        />
        <section
          className="mb-6 rounded-2xl border border-[#c9ddd3] bg-[#eaf3ee] p-5 sm:p-6"
          aria-labelledby="completion-heading"
          data-completion-summary
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-bold uppercase tracking-[.14em] text-[#276955]">
                A good start
              </p>
              <h2
                className="mt-1 text-xl font-semibold"
                id="completion-heading"
              >
                Profile completion
              </h2>
              <p
                className="mt-2 text-sm leading-6 text-[#4b5563]"
                data-completion-message
              >
                Loading your profile requirements…
              </p>
            </div>
            <span className="rounded-full border border-[#bfd4c9] bg-white px-3 py-1.5 text-xs font-semibold text-[#276955]">
              You control visibility
            </span>
          </div>
        </section>
        <form className="grid gap-6" noValidate>
          <input type="hidden" name="etag" />
          <section className={card} aria-labelledby="profile-heading">
            <div className="mb-5 border-b border-[#e8ebe5] pb-4">
              <p className="text-xs font-bold uppercase tracking-[.13em] text-[#a76f15]">
                The essentials
              </p>
              <h2
                className="mt-1 font-serif text-2xl font-semibold"
                id="profile-heading"
              >
                Profile facts
              </h2>
              <p className="mt-1 text-sm text-[#4b5563]">
                Share the details you are comfortable including.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className={label}>
                Full name
                <input
                  className={field}
                  name="full_name"
                  autoComplete="name"
                  required
                  maxLength={200}
                />
              </label>
              <label className={label}>
                Location
                <input
                  className={field}
                  name="location"
                  autoComplete="address-level2"
                  required
                />
              </label>
              <label className={label}>
                Experience in years
                <input
                  className={field}
                  name="experience_years"
                  type="number"
                  min="0"
                  step="0.01"
                  required
                />
              </label>
              <label className={label}>
                Skills
                <input
                  className={field}
                  name="skills"
                  required
                  aria-describedby="skills-help"
                />
              </label>
            </div>
            <small
              className="mt-2 block text-xs text-[#6f756c]"
              id="skills-help"
            >
              Separate skills with commas.
            </small>
            <label className={`${label} mt-5`}>
              Meaningful work
              <textarea
                className={`${field} min-h-28 resize-y`}
                name="meaningful_work"
                maxLength={300}
                aria-describedby="meaningful-count"
              />
            </label>
            <output
              className="mt-1 block text-right text-xs text-[#818b98]"
              id="meaningful-count"
              htmlFor="meaningful_work"
            >
              0 / 300
            </output>
          </section>
          <section className={card} aria-labelledby="employment-heading">
            <div className="mb-5 border-b border-[#e8ebe5] pb-4">
              <p className="text-xs font-bold uppercase tracking-[.13em] text-[#a76f15]">
                Your story
              </p>
              <h2
                className="mt-1 font-serif text-2xl font-semibold"
                id="employment-heading"
              >
                Employment history
              </h2>
              <p className="mt-1 text-sm leading-6 text-[#4b5563]">
                Missing or uncertain dates can stay unconfirmed. We do not
                invent them.
              </p>
            </div>
            <div className="grid gap-3" data-employment-list />
            <button
              className={`${secondaryButton} mt-4`}
              type="button"
              data-add-employment
            >
              Add employment record
            </button>
          </section>
          <section className={card} aria-labelledby="preferences-heading">
            <div className="mb-5 border-b border-[#e8ebe5] pb-4">
              <p className="text-xs font-bold uppercase tracking-[.13em] text-[#a76f15]">
                What suits you
              </p>
              <h2
                className="mt-1 font-serif text-2xl font-semibold"
                id="preferences-heading"
              >
                Opportunity preferences
              </h2>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className={label}>
                Preferred roles
                <input className={field} name="role_categories" />
              </label>
              <label className={label}>
                Preferred locations
                <input className={field} name="preferred_locations" />
              </label>
            </div>
            <fieldset className="mt-5 rounded-lg border border-[#d7dbd2] p-4">
              <legend className="px-1 text-sm font-semibold">
                Work arrangements
              </legend>
              <div className="mt-2 flex flex-wrap gap-x-6 gap-y-3">
                {[
                  ["FLEXIBLE", "Flexible"],
                  ["REMOTE", "Remote"],
                  ["HYBRID", "Hybrid"],
                  ["ON_SITE", "On-site"],
                ].map(([value, text]) => (
                  <label
                    className="flex items-center gap-2 text-sm text-[#34374c]"
                    key={value}
                  >
                    <input
                      className="size-4 accent-[#276955]"
                      type="checkbox"
                      name="work_arrangements"
                      value={value}
                    />
                    {text}
                  </label>
                ))}
              </div>
            </fieldset>
          </section>
          <section className={card} aria-labelledby="visibility-heading">
            <div className="mb-5 border-b border-[#e8ebe5] pb-4">
              <p className="text-xs font-bold uppercase tracking-[.13em] text-[#a76f15]">
                You are in control
              </p>
              <h2
                className="mt-1 font-serif text-2xl font-semibold"
                id="visibility-heading"
              >
                Visibility and consent
              </h2>
              <p className="mt-1 text-sm leading-6 text-[#4b5563]">
                Choose who can discover your profile. You can change this at any
                time.
              </p>
            </div>
            <fieldset className="grid gap-3 border-0 p-0 sm:grid-cols-2">
              {[
                [
                  "APPROVED_RECRUITERS",
                  "Approved recruiters",
                  "Only the companies you name.",
                ],
                [
                  "MATCHING_ROLES",
                  "Matching roles",
                  "Recruiters with roles that fit your preferences.",
                ],
                [
                  "APPLIED_ROLES_ONLY",
                  "Roles you apply to",
                  "Only teams connected to your applications.",
                ],
                [
                  "NOT_LOOKING",
                  "Not looking right now",
                  "Your profile stays hidden from search.",
                ],
              ].map(([value, title, detail]) => (
                <label
                  className="flex cursor-pointer items-start gap-3 rounded-lg border border-[#d7dbd2] bg-[#fafbf8] p-4 transition has-checked:border-[#276955] has-checked:bg-[#eaf3ee]"
                  key={value}
                >
                  <input
                    className="mt-1 size-4 accent-[#276955]"
                    type="radio"
                    name="visibility"
                    value={value}
                    defaultChecked={value === "NOT_LOOKING"}
                  />
                  <span>
                    <strong className="block text-sm font-semibold">
                      {title}
                    </strong>
                    <span className="mt-1 block text-xs leading-5 text-[#4b5563]">
                      {detail}
                    </span>
                  </span>
                </label>
              ))}
            </fieldset>
            <label className={`${label} mt-5`}>
              Approved company tenant IDs
              <input
                className={field}
                name="approved_tenant_ids"
                aria-describedby="approved-help"
              />
            </label>
            <small
              className="mt-1 block text-xs text-[#6f756c]"
              id="approved-help"
            >
              Required only for Approved recruiters; separate IDs with commas.
            </small>
            <p className="mt-4 rounded-md bg-[#fafbf8] p-3 text-xs leading-5 text-[#4b5563]">
              Saving records affirmative consent for recruiting discovery under
              the audience you selected.
            </p>
          </section>
          <section className={card} aria-labelledby="resume-heading">
            <div className="mb-5 border-b border-[#e8ebe5] pb-4">
              <p className="text-xs font-bold uppercase tracking-[.13em] text-[#a76f15]">
                Optional document
              </p>
              <h2
                className="mt-1 font-serif text-2xl font-semibold"
                id="resume-heading"
              >
                Resume
              </h2>
              <p className="mt-1 text-sm text-[#4b5563]">
                You will review extracted suggestions before they update your
                profile.
              </p>
            </div>
            <label className={label}>
              Choose PDF, DOC, or DOCX, up to 10 MB
              <input
                className={`${field} file:mr-4 file:rounded file:border-0 file:bg-[#eaf3ee] file:px-3 file:py-2 file:font-semibold file:text-[#276955]`}
                type="file"
                data-resume
                accept=".pdf,.doc,.docx"
              />
            </label>
            <div
              className="mt-3 text-sm text-[#4b5563]"
              data-resume-status
              role="status"
              aria-live="polite"
            >
              No file selected.
            </div>
            <div className="mt-3" data-resume-suggestions aria-live="polite" />
          </section>
          <div className="sticky bottom-3 z-20 flex flex-wrap justify-end gap-3 rounded-xl border border-[#d7dbd2] bg-white/95 p-3 shadow-lg backdrop-blur sm:p-4">
            <button className={secondaryButton} type="submit">
              Save profile
            </button>
            <button className={button} type="button" data-publish>
              Publish profile
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

function mount() {
  const recruiter = document.querySelector<HTMLElement>(
    "[data-react-recruiter-search]",
  );
  if (recruiter) {
    const root = createRoot(recruiter);
    flushSync(() =>
      root.render(
        <RecruiterSearch
          root={
            recruiter as HTMLElement & {
              dataset: DOMStringMap & { tenantId?: string };
            }
          }
        />,
      ),
    );
  }
  const candidate = document.querySelector<HTMLElement>(
    "[data-react-candidate-profile]",
  );
  if (candidate) {
    const root = createRoot(candidate);
    flushSync(() => root.render(<CandidateProfile />));
  }
}

mount();
