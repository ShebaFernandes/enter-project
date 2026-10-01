// Test-only component states, not production fixtures or workflow behavior.
import { useState } from "react";
import {
  mountPage,
  AppShell,
  WorkspaceNavigation,
  ResponsiveGrid,
  Card,
  Button,
  IconButton,
  Field,
  TextInput,
  Textarea,
  Select,
  Checkbox,
  Radio,
  Chip,
  Alert,
  StatusMessage,
  Loading,
  EmptyState,
  DegradedState,
  ErrorState,
  Dialog,
  ConflictPanel,
  Table,
  List,
} from "../../../frontend/react/foundation";

function Showcase() {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [value, setValue] = useState("");
  const [status, setStatus] = useState(
    "Component examples only — no candidate data or production actions.",
  );
  const [conflict, setConflict] = useState(false);
  const done = (message: string) => {
    setConflict(false);
    setStatus(message);
  };
  return (
    <AppShell
      title="Shared design foundation"
      navigation={
        <WorkspaceNavigation
          label="Fixture sections"
          items={[
            { label: "Components", href: "#components", current: true },
            { label: "States", href: "#states" },
          ]}
        />
      }
    >
      <StatusMessage>{status}</StatusMessage>
      <ResponsiveGrid>
        <Card title="Clear, considered controls">
          <p className="ui-help">
            Paper surfaces, quiet borders and purposeful accents.
          </p>
          <div className="ui-row">
            <Button onClick={() => setStatus("Example action completed.")}>
              Primary action
            </Button>
            <Button variant="secondary">Secondary</Button>
            <Button disabled>Unavailable action</Button>
            <IconButton label="Example information">i</IconButton>
          </div>
          <div className="ui-row">
            <Chip tone="sage">Ready</Chip>
            <Chip tone="gold">Needs review</Chip>
            <Chip tone="clay">Action required</Chip>
            <Chip tone="unknown">Unknown</Chip>
            <Chip>Unavailable</Chip>
          </div>
          <Button variant="secondary" onClick={() => setOpen(true)}>
            Open dialog
          </Button>
        </Card>
        <Card title="Labels and validation">
          <form
            id="components"
            className="ui-stack"
            onSubmit={(event) => {
              event.preventDefault();
              setError(value ? "" : "Enter a value for this example.");
              setStatus(
                value ? "Example validated." : "Review the marked field.",
              );
            }}
          >
            <Field
              label="Example label"
              help="A descriptive label stays visible."
              error={error}
            >
              {(props) => (
                <TextInput
                  {...props}
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                />
              )}
            </Field>
            <Field
              label="Optional description"
              help="Keep your explanation concise."
            >
              {(props) => <Textarea {...props} />}
            </Field>
            <Field label="Example selection">
              {(props) => (
                <Select {...props}>
                  <option>Choose an option</option>
                  <option>Option one</option>
                </Select>
              )}
            </Field>
            <Checkbox label="Example preference" />
            <fieldset>
              <legend>Example choices</legend>
              <Radio
                name="example-choice"
                label="First choice"
                value="first"
                defaultChecked
              />
              <Radio
                name="example-choice"
                label="Second choice"
                value="second"
              />
            </fieldset>
            <Button type="submit">Validate example</Button>
          </form>
        </Card>
        <Card title="Feedback and recovery">
          <div id="states" className="ui-stack">
            <Loading label="Loading current information…" />
            <Alert>Example validation: review the highlighted field.</Alert>
            <DegradedState>
              Optional assistance is unavailable. Manual entry remains
              available.
            </DegradedState>
            <ErrorState
              onRetry={() =>
                setStatus("Retry requested explicitly; no mutation replayed.")
              }
            />
            <Button variant="secondary" onClick={() => setConflict(true)}>
              Show conflict
            </Button>
          </div>
          {conflict && (
            <ConflictPanel
              conflict={{
                current: { example: "Stored example" },
                attempted: { example: "Edited example" },
                changed_fields: ["example"],
                current_etag: '"2"',
              }}
              onDiscard={() => done("Stored version selected.")}
              onReview={() =>
                done("Review requested. Changes are not submitted.")
              }
              onResubmit={() =>
                done("Explicit resubmission requested with current version.")
              }
            />
          )}
        </Card>
        <EmptyState
          title="Nothing here yet"
          action={
            <Button
              variant="secondary"
              onClick={() => setStatus("Start action selected.")}
            >
              Start when ready
            </Button>
          }
        >
          Current authorized information will appear here. No placeholder
          records are shown.
        </EmptyState>
      </ResponsiveGrid>
      <Card title="Structured information">
        <Table
          caption="Component state reference"
          columns={["State", "Meaning"]}
          rows={[
            ["Known", "Evidence is available"],
            ["Unknown", "Not supplied; never inferred"],
            ["Unavailable", "Not disclosed in the current context"],
          ]}
        />
        <List>
          <li>Every status includes a text label.</li>
          <li>
            Long content wraps without hiding controls or changing reading
            order.
          </li>
        </List>
      </Card>
      <Dialog open={open} onClose={() => setOpen(false)} title="Review changes">
        <p>Nothing is submitted by opening or closing this example.</p>
        <Button variant="secondary" onClick={() => setOpen(false)}>
          Keep editing
        </Button>
      </Dialog>
    </AppShell>
  );
}
void mountPage({ "foundation-fixture": Showcase }).catch(() => {
  /* Static recovery content remains visible. */
});
