import type { ComponentProps, ReactNode } from "react";
import { Card, Checkbox, StatusMessage } from "./components";

// Semantic presentation boundaries. The page coordinates fresh authorized reads
// and keeps each aggregate's drafts in memory; these components own no policy.
type PanelProps = { children: ReactNode };
export function NotesPanel({ children }: PanelProps) {
  return <Card title="Recruiter notes">{children}</Card>;
}
export function InternalStatus({ children }: PanelProps) {
  return <Card title="Internal status and shortlist">{children}</Card>;
}
export function ShortlistControl(
  props: Omit<ComponentProps<typeof Checkbox>, "label">,
) {
  return <Checkbox {...props} label="Shortlisted" />;
}
export function PublicationPreview({ children }: PanelProps) {
  return <Card title="Candidate-facing publication">{children}</Card>;
}
export function DisclosurePreview({ children }: PanelProps) {
  return <Card title="Contact and team sharing">{children}</Card>;
}
export function DeliveryFeedback({ children }: PanelProps) {
  return <StatusMessage>{children}</StatusMessage>;
}
