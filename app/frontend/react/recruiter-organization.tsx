import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  Alert,
  AppShell,
  Button,
  Card,
  Checkbox,
  Chip,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  Select,
  StatusMessage,
  Textarea,
  TextInput,
  WorkspaceNavigation,
} from "./components";
import type { PageProps } from "./mount";
import { visualAssets } from "./visual-assets";

type Request = PageProps["request"];
type Unit = {
  id: string;
  name: string;
  description: string;
  status: "ACTIVE" | "INACTIVE";
  version: number;
};
type Opening = {
  id: string;
  business_unit_id: string;
  title: string;
  location: { display?: string };
  work_mode: string;
  employment_type: string;
  description: string;
  state: "DRAFT" | "OPEN" | "PAUSED" | "CLOSED";
  version: number;
};
type Synthetic = {
  id: string;
  display_name: string;
  source_type: "RECRUITER_ENTERED_SYNTHETIC";
  source_label: string;
  location: { display?: string };
  experience_years: string;
  skills: string[];
};
type Saved = {
  id: string;
  name: string;
  search_id: string;
  criteria: { context: { type: string; opening_id?: string } };
  changed_since_save: string[];
};
type Publication = {
  internal_state: Opening["state"];
  publication_state: "PUBLISHED" | "UNPUBLISHED";
  public_fields: Record<string, string | null>;
  public_url: string | null;
  source_etag: string;
  preview_digest: string;
};
const jsonHeaders = () => ({
  "Content-Type": "application/json",
  "Idempotency-Key": crypto.randomUUID(),
});

export function BusinessUnitEditor({
  units,
  base,
  request,
  reload,
}: {
  units: Unit[];
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setMessage("Creating business unit…");
    const response = await request(`${base}/business-units`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        name: data.get("name"),
        description: data.get("description"),
      }),
    });
    setMessage(
      response.ok ? "Business unit created." : "Business unit was not created.",
    );
    if (response.ok) {
      form.reset();
      reload();
    }
  };
  return (
    <Card title="Business units">
      <p>
        Business units organize openings inside this tenant. They do not create
        a new security boundary.
      </p>
      <form className="fm12-form" onSubmit={(e) => void submit(e)}>
        <Field label="Business unit name">
          {(props) => (
            <TextInput {...props} name="name" required maxLength={300} />
          )}
        </Field>
        <Field label="Description (optional)">
          {(props) => (
            <Textarea {...props} name="description" maxLength={2000} />
          )}
        </Field>
        <Button type="submit">Create business unit</Button>
      </form>
      <StatusMessage>{message}</StatusMessage>
      {units.length ? (
        <ul className="fm12-list">
          {units.map((unit) => (
            <li key={unit.id}>
              <strong>{unit.name}</strong>
              <Chip tone={unit.status === "ACTIVE" ? "sage" : "gold"}>
                {unit.status.toLowerCase()}
              </Chip>
              <p>{unit.description || "No description"}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p>No business units yet.</p>
      )}
    </Card>
  );
}

function PublicationPanel({
  opening,
  base,
  request,
  reload,
}: {
  opening: Opening;
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [preview, setPreview] = useState<Publication>();
  const [reviewed, setReviewed] = useState(false);
  const [message, setMessage] = useState("");
  const [decision, setDecision] = useState<"publish" | "withdraw">();
  const load = useCallback(
    async (show = false) => {
      setMessage("Loading publication status…");
      const response = await request(
        `${base}/openings/${opening.id}/publication`,
      );
      if (!response.ok) {
        setMessage("Publication is unavailable. Your access may have changed.");
        return;
      }
      setPreview((await response.json()) as Publication);
      setReviewed(show);
      setMessage(
        show
          ? "Preview ready. Only these reviewed fields will be public."
          : "Publication status loaded.",
      );
    },
    [base, opening.id, request],
  );
  useEffect(() => void load(false), [load]);
  const changeState = async (state: "OPEN" | "PAUSED" | "CLOSED") => {
    if (!preview) return;
    const response = await request(`${base}/openings/${opening.id}`, {
      method: "PATCH",
      headers: { ...jsonHeaders(), "If-Match": preview.source_etag },
      body: JSON.stringify({ state }),
    });
    if (response.status === 409)
      setMessage(
        "This opening changed elsewhere. Nothing was overwritten; refresh the preview.",
      );
    else if (!response.ok) setMessage("Opening state was not changed.");
    else {
      setMessage(
        `Opening changed to ${state}. Public publication remains separate.`,
      );
      reload();
      void load(false);
    }
  };
  const confirm = async () => {
    if (!preview || !decision) return;
    const response = await request(
      `${base}/openings/${opening.id}/publication/${decision}`,
      {
        method: "POST",
        headers: { ...jsonHeaders(), "If-Match": preview.source_etag },
        body: JSON.stringify({
          confirmed: true,
          ...(decision === "publish"
            ? { preview_digest: preview.preview_digest }
            : {}),
        }),
      },
    );
    setDecision(undefined);
    if (response.status === 409) {
      setMessage(
        "This opening or preview changed. Nothing was published; preview again.",
      );
      setReviewed(false);
      return;
    }
    if (!response.ok) {
      setMessage("Publication was not changed. Review a fresh preview.");
      return;
    }
    setPreview((await response.json()) as Publication);
    setReviewed(false);
    setMessage(
      decision === "publish"
        ? "Publication saved. This role is now public."
        : "Publication withdrawn. Internal opening state unchanged.",
    );
  };
  return (
    <section
      className="fm12-publication"
      aria-label={`Publication for ${opening.title}`}
    >
      <div className="fm12-meta">
        <span>
          Internal: <strong>{preview?.internal_state ?? opening.state}</strong>
        </span>
        <span>
          Public: <strong>{preview?.publication_state ?? "Loading"}</strong>
        </span>
      </div>
      {preview?.public_url && <a href={preview.public_url}>View public role</a>}
      {reviewed && preview && (
        <dl className="fm12-preview">
          {Object.entries(preview.public_fields).map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>
                {value ||
                  (key === "published_at"
                    ? "Assigned when confirmed"
                    : "Not provided")}
              </dd>
            </div>
          ))}
        </dl>
      )}
      <div className="ui-row">
        <Button variant="secondary" onClick={() => void load(true)}>
          Preview
        </Button>
        {preview?.internal_state === "DRAFT" ||
        preview?.internal_state === "PAUSED" ? (
          <Button variant="secondary" onClick={() => void changeState("OPEN")}>
            Open internally (does not publish)
          </Button>
        ) : null}
        {preview?.internal_state === "OPEN" && (
          <Button
            variant="secondary"
            onClick={() => void changeState("PAUSED")}
          >
            Pause internally
          </Button>
        )}
        <Button
          disabled={!reviewed || preview?.internal_state !== "OPEN"}
          onClick={() => setDecision("publish")}
        >
          {preview?.publication_state === "PUBLISHED"
            ? "Update publication"
            : "Publish"}
        </Button>
        <Button
          variant="danger"
          disabled={preview?.publication_state !== "PUBLISHED"}
          onClick={() => setDecision("withdraw")}
        >
          Withdraw publication
        </Button>
      </div>
      <StatusMessage>{message}</StatusMessage>
      <Dialog
        open={Boolean(decision)}
        onClose={() => setDecision(undefined)}
        title={
          decision === "publish"
            ? "Confirm public publication"
            : "Confirm public withdrawal"
        }
      >
        <p>
          {decision === "publish"
            ? "Publish the reviewed allowlisted fields to anyone visiting the public jobs directory?"
            : "Remove this role from public discovery immediately? Its internal opening state will not change."}
        </p>
        <div className="ui-row">
          <Button
            variant={decision === "publish" ? "primary" : "danger"}
            onClick={() => void confirm()}
          >
            {decision === "publish"
              ? "Confirm publication"
              : "Confirm withdrawal"}
          </Button>
          <Button variant="secondary" onClick={() => setDecision(undefined)}>
            Cancel
          </Button>
        </div>
      </Dialog>
    </section>
  );
}

export function OpeningEditor({
  openings,
  units,
  base,
  request,
  reload,
}: {
  openings: Opening[];
  units: Unit[];
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = await request(`${base}/openings`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        business_unit_id: data.get("business_unit_id"),
        title: data.get("title"),
        description: data.get("description"),
        location: { display: data.get("location") },
        work_mode: data.get("work_mode"),
        employment_type: data.get("employment_type"),
      }),
    });
    setMessage(
      response.ok
        ? "Opening created as an internal draft."
        : "Opening was not created.",
    );
    if (response.ok) {
      form.reset();
      reload();
    }
  };
  return (
    <Card title="Openings">
      <p>
        Internal opening state and public publication are deliberately separate.
      </p>
      <form
        className="fm12-form fm12-form-grid"
        onSubmit={(e) => void submit(e)}
      >
        <Field label="Business unit">
          {(props) => (
            <Select {...props} name="business_unit_id" required defaultValue="">
              <option value="" disabled>
                Select a unit
              </option>
              {units
                .filter((u) => u.status === "ACTIVE")
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name}
                  </option>
                ))}
            </Select>
          )}
        </Field>
        <Field label="Opening title">
          {(props) => (
            <TextInput {...props} name="title" required maxLength={300} />
          )}
        </Field>
        <Field label="Location">
          {(props) => <TextInput {...props} name="location" required />}
        </Field>
        <Field label="Work arrangement">
          {(props) => (
            <Select {...props} name="work_mode">
              <option>REMOTE</option>
              <option>HYBRID</option>
              <option>ON_SITE</option>
              <option>FLEXIBLE</option>
            </Select>
          )}
        </Field>
        <Field label="Employment type">
          {(props) => (
            <TextInput
              {...props}
              name="employment_type"
              defaultValue="PERMANENT"
              required
            />
          )}
        </Field>
        <Field label="Description (optional)">
          {(props) => (
            <Textarea {...props} name="description" maxLength={20000} />
          )}
        </Field>
        <Button
          type="submit"
          disabled={!units.some((u) => u.status === "ACTIVE")}
        >
          Create opening
        </Button>
      </form>
      <StatusMessage>{message}</StatusMessage>
      <div className="fm12-opening-list">
        {openings.map((opening) => (
          <article className="fm12-opening" key={opening.id}>
            <div className="fm12-card-head">
              <div>
                <p className="fm12-kicker">
                  {units.find((u) => u.id === opening.business_unit_id)?.name ??
                    "Business unit"}
                </p>
                <h3>{opening.title}</h3>
              </div>
              <Chip tone={opening.state === "OPEN" ? "sage" : "gold"}>
                {opening.state.toLowerCase()}
              </Chip>
            </div>
            <p>{opening.description || "No internal description"}</p>
            <PublicationPanel
              opening={opening}
              base={base}
              request={request}
              reload={reload}
            />
          </article>
        ))}
      </div>
      {openings.length === 0 && <p>No openings yet.</p>}
    </Card>
  );
}

export function SyntheticCandidatePanel({
  items,
  base,
  request,
  reload,
}: {
  items: Synthetic[];
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = await request(`${base}/recruiter-entered-candidates`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        display_name: data.get("display_name"),
        location: { display: data.get("location") },
        experience_years: data.get("experience_years"),
        skills: String(data.get("skills") ?? "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean),
        confirm_synthetic: confirmed,
      }),
    });
    setMessage(
      response.ok
        ? "Synthetic candidate created with immutable provenance."
        : "Synthetic candidate was not created.",
    );
    if (response.ok) {
      form.reset();
      setConfirmed(false);
      reload();
    }
  };
  return (
    <Card title="Synthetic candidate fixtures">
      <Alert tone="gold">
        <strong>Test data only.</strong> These records cannot contain real
        candidate details, contact information or resumes, and never merge with
        candidate-controlled profiles.
      </Alert>
      <form
        className="fm12-form fm12-form-grid"
        onSubmit={(e) => void submit(e)}
      >
        <Field label="Synthetic display name">
          {(props) => <TextInput {...props} name="display_name" required />}
        </Field>
        <Field label="Synthetic location">
          {(props) => <TextInput {...props} name="location" required />}
        </Field>
        <Field label="Experience years">
          {(props) => (
            <TextInput
              {...props}
              name="experience_years"
              type="number"
              min="0"
              step="0.01"
              required
            />
          )}
        </Field>
        <Field label="Synthetic skills" help="Separate skills with commas.">
          {(props) => <TextInput {...props} name="skills" required />}
        </Field>
        <Checkbox
          label="I confirm this is entirely synthetic test data."
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
          required
        />
        <Button type="submit" disabled={!confirmed}>
          Create synthetic candidate
        </Button>
      </form>
      <StatusMessage>{message}</StatusMessage>
      <ul className="fm12-list">
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.display_name}</strong>
            <p>{item.source_label}</p>
            <p>{item.skills.join(", ")}</p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function SavedSearchManager({
  items,
  base,
  request,
  reload,
}: {
  items: Saved[];
  base: string;
  request: Request;
  reload: () => void;
}) {
  const [message, setMessage] = useState("");
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = await request(`${base}/saved-searches`, {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        name: data.get("name"),
        search_id: data.get("search_id"),
      }),
    });
    setMessage(
      response.ok
        ? "Search saved from its authoritative criteria context."
        : "Search was not saved.",
    );
    if (response.ok) {
      form.reset();
      reload();
    }
  };
  return (
    <Card title="Saved searches">
      <p>
        Opening context comes only from the selected search definition. It
        cannot be supplied independently here.
      </p>
      <form className="fm12-form" onSubmit={(e) => void submit(e)}>
        <Field label="Saved-search name">
          {(props) => (
            <TextInput {...props} name="name" required maxLength={200} />
          )}
        </Field>
        <Field label="Owned search ID">
          {(props) => <TextInput {...props} name="search_id" required />}
        </Field>
        <Button type="submit">Save search</Button>
      </form>
      <StatusMessage>{message}</StatusMessage>
      <ul className="fm12-list">
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.name}</strong>
            <p>
              {item.criteria.context.type}
              {item.criteria.context.opening_id
                ? ` · opening ${item.criteria.context.opening_id}`
                : ""}
            </p>
            {item.changed_since_save.length > 0 && (
              <Alert tone="gold">
                Changed since save: {item.changed_since_save.join(", ")}
              </Alert>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function OrganizationPage({ bootstrap, request }: PageProps) {
  const tenantId = bootstrap.tenantId ?? "";
  const base = `/api/v1/tenants/${tenantId}`;
  const [units, setUnits] = useState<Unit[]>([]);
  const [openings, setOpenings] = useState<Opening[]>([]);
  const [synthetic, setSynthetic] = useState<Synthetic[]>([]);
  const [saved, setSaved] = useState<Saved[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const load = useCallback(async () => {
    setFailed(false);
    try {
      const responses = await Promise.all(
        [
          "business-units",
          "openings",
          "recruiter-entered-candidates",
          "saved-searches",
        ].map((path) => request(`${base}/${path}`)),
      );
      if (responses.some((response) => !response.ok)) throw new Error();
      const [nextUnits, nextOpenings, nextSynthetic, nextSaved] =
        await Promise.all(responses.map((response) => response.json()));
      setUnits(nextUnits as Unit[]);
      setOpenings(nextOpenings as Opening[]);
      setSynthetic(nextSynthetic as Synthetic[]);
      setSaved(nextSaved as Saved[]);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [base, request]);
  useEffect(() => void load(), [load]);
  const navigation = (
    <WorkspaceNavigation
      label="Recruiter navigation"
      items={[
        { label: "Search", href: `/tenants/${tenantId}/recruiter/search/` },
        {
          label: "Organization",
          href: `/tenants/${tenantId}/recruiter/organization/`,
          current: true,
        },
      ]}
    />
  );
  return (
    <AppShell title="Hiring organization" navigation={navigation}>
      <p>
        Manage organization context, internal openings and synthetic-only
        recruitment fixtures inside the current tenant.
      </p>
      {loading && <Loading label="Loading organization…" />}
      {failed && <ErrorState onRetry={() => void load()} />}
      {!loading && !failed && (
        <div className="fm12-grid">
          <BusinessUnitEditor
            units={units}
            base={base}
            request={request}
            reload={() => void load()}
          />
          <OpeningEditor
            openings={openings}
            units={units}
            base={base}
            request={request}
            reload={() => void load()}
          />
          <SyntheticCandidatePanel
            items={synthetic}
            base={base}
            request={request}
            reload={() => void load()}
          />
          <SavedSearchManager
            items={saved}
            base={base}
            request={request}
            reload={() => void load()}
          />
        </div>
      )}
      {!loading &&
        !failed &&
        !units.length &&
        !openings.length &&
        !synthetic.length &&
        !saved.length && (
          <EmptyState
            title="Organization is ready"
            illustration={{
              src: visualAssets.organizationSetupEmpty,
              width: 1024,
              height: 1024,
            }}
          >
            Create a business unit to begin.
          </EmptyState>
        )}
    </AppShell>
  );
}
