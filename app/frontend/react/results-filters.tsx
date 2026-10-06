import { useState } from "react";
import { Button, Field, TextInput, Select, Alert } from "./components";
import type { Criteria } from "./criteria-review";
import type { PageProps } from "./mount";
import { responseJson } from "../shared/api-client";
import { workflowTransport } from "../shared/workflow-handoff";
export function ResultsFilters({
  criteria,
  tenant,
  request,
  onClose,
  count,
}: {
  criteria: Criteria | null;
  tenant: string;
  request: PageProps["request"];
  onClose: () => void;
  count: number;
}) {
  const [keywords, setKeywords] = useState("");
  const [match, setMatch] = useState("ANY");
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [location, setLocation] = useState("");
  const [notice, setNotice] = useState("");
  const [currentRole, setCurrentRole] = useState("");
  const [currentCompany, setCurrentCompany] = useState("");
  const [education, setEducation] = useState("");
  const [arrangement, setArrangement] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [completed, setCompleted] = useState<string | null>(null);
  async function apply() {
    if (!criteria || busy) return;
    if (min && max && Number(min) > Number(max)) {
      setError("Minimum experience must not exceed maximum experience.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      let id = completed;
      if (!id) {
        const next: Criteria = JSON.parse(JSON.stringify(criteria));
        const replaced = new Set<string>();
        if (min || max) replaced.add("experience_years");
        if (location.trim()) replaced.add("location");
        if (notice) replaced.add("notice_period");
        if (currentRole.trim()) replaced.add("current_role");
        if (currentCompany.trim()) replaced.add("current_company");
        if (education.trim()) replaced.add("education");
        if (arrangement) replaced.add("work_arrangement");
        next.criteria = next.criteria.filter(
          (item) => !replaced.has(item.field),
        );
        next.groups = next.groups.filter((group) =>
          next.criteria.some((item) => item.group_id === group.id),
        );
        const add = (
          field: string,
          operator: string,
          value: unknown,
          groupId: string,
        ) =>
          next.criteria.push({
            id: crypto.randomUUID(),
            group_id: groupId,
            field,
            operator,
            value,
          } as Criteria["criteria"][number]);
        const group = (operator: "ANY" | "ALL") => {
          const id = crypto.randomUUID();
          next.groups.push({ id, purpose: "REQUIREMENT", operator });
          return id;
        };
        const terms = keywords
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean);
        if (terms.length) {
          const id = group(match as "ANY" | "ALL");
          terms.forEach((term) => add("resume_keyword", "CONTAINS", term, id));
        }
        if (min || max || notice) {
          const id = group("ALL");
          if (min) add("experience_years", "GTE", Number(min), id);
          if (max) add("experience_years", "LTE", Number(max), id);
          if (notice) add("notice_period", "EQ", notice, id);
        }
        if (
          currentRole.trim() ||
          currentCompany.trim() ||
          education.trim() ||
          arrangement
        ) {
          const id = group("ALL");
          if (currentRole.trim())
            add("current_role", "CONTAINS", currentRole.trim(), id);
          if (currentCompany.trim())
            add("current_company", "CONTAINS", currentCompany.trim(), id);
          if (education.trim())
            add("education", "CONTAINS", education.trim(), id);
          if (arrangement) add("work_arrangement", "EQ", arrangement, id);
        }
        const locations = location
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean);
        if (locations.length) {
          const id = group("ANY");
          locations.forEach((value) => add("location", "EQ", value, id));
        }
        const { data } = await responseJson<{ search_id: string }>(
          await request(`/api/v1/tenants/${tenant}/searches`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(next),
          }),
        );
        id = data.search_id;
        setCompleted(id);
      }
      const transport = workflowTransport(tenant);
      const token = await transport.create("search-results", { search_id: id });
      transport.navigate("search-results", token);
    } catch {
      setError(
        "The filtered results could not be opened. Your current results remain available.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <aside
      className="results-filter-panel"
      aria-label="Filter results panel"
      id="results-filter-panel"
    >
      <h2>Filter results</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void apply();
        }}
      >
        <fieldset disabled={busy || Boolean(completed)}>
          <section>
            <Field
              label="Find in resume"
              help="Searches reviewed profile details and resume text where access is permitted."
            >
              {(props) => (
                <TextInput
                  {...props}
                  placeholder="Keywords separated by commas"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                />
              )}
            </Field>
            <div className="filter-match-options">
              {["ANY", "ALL"].map((v) => (
                <label key={v}>
                  <input
                    type="radio"
                    name="keyword-match"
                    checked={match === v}
                    onChange={() => setMatch(v)}
                  />
                  Match {v.toLowerCase()}
                </label>
              ))}
            </div>
          </section>
          <section>
            <h3>Work experience</h3>
            <Field label="Current or recent role">
              {(p) => (
                <TextInput
                  {...p}
                  placeholder="Backend engineer"
                  value={currentRole}
                  onChange={(e) => setCurrentRole(e.target.value)}
                />
              )}
            </Field>
            <Field label="Current company">
              {(p) => (
                <TextInput
                  {...p}
                  placeholder="Company name"
                  value={currentCompany}
                  onChange={(e) => setCurrentCompany(e.target.value)}
                />
              )}
            </Field>
            <div className="filter-pair">
              <Field label="Minimum years">
                {(p) => (
                  <TextInput
                    {...p}
                    type="number"
                    min="0"
                    max="80"
                    step="0.1"
                    value={min}
                    onChange={(e) => setMin(e.target.value)}
                  />
                )}
              </Field>
              <Field label="Maximum years">
                {(p) => (
                  <TextInput
                    {...p}
                    type="number"
                    min="0"
                    max="80"
                    step="0.1"
                    value={max}
                    onChange={(e) => setMax(e.target.value)}
                  />
                )}
              </Field>
            </div>
          </section>
          <section>
            <Field label="School or college">
              {(p) => (
                <TextInput
                  {...p}
                  placeholder="Institute name"
                  value={education}
                  onChange={(e) => setEducation(e.target.value)}
                />
              )}
            </Field>
            <Field label="Work arrangement">
              {(p) => (
                <Select
                  {...p}
                  value={arrangement}
                  onChange={(e) => setArrangement(e.target.value)}
                >
                  <option value="">Any</option>
                  <option value="REMOTE">Remote</option>
                  <option value="HYBRID">Hybrid</option>
                  <option value="ON_SITE">On-site</option>
                  <option value="FLEXIBLE">Flexible</option>
                </Select>
              )}
            </Field>
          </section>
          <section>
            <Field label="Current locations">
              {(p) => (
                <TextInput
                  {...p}
                  placeholder="Bengaluru, Mumbai"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              )}
            </Field>
          </section>
          <section>
            <Field label="Notice period">
              {(p) => (
                <Select
                  {...p}
                  value={notice}
                  onChange={(e) => setNotice(e.target.value)}
                >
                  <option value="">All</option>
                  {[
                    "Immediate",
                    "15 days",
                    "30 days",
                    "60 days",
                    "90 days",
                  ].map((n) => (
                    <option key={n}>{n}</option>
                  ))}
                </Select>
              )}
            </Field>
          </section>
          <section className="filter-data-note">
            <h3>Evidence boundary</h3>
            <p>
              Filters use candidate-confirmed profile and resume details.
              Unknown values never count as matches.
            </p>
          </section>
        </fieldset>
        {error && <Alert>{error}</Alert>}
        <footer>
          <span>{count} loaded results</span>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" busy={busy} disabled={!criteria}>
            {completed ? "Open results" : "Apply"}
          </Button>
        </footer>
      </form>
    </aside>
  );
}
