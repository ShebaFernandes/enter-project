export type CandidateFinding = {
  code: "SHORT_TENURE";
  informational_only: true;
  message: string;
  evidence: {
    employment_record_id: string;
    company: string;
    confirmed_start_date: string;
    confirmed_end_date: string;
    calculated_duration: { calendar_months: number; remaining_days: number };
    calculation_version: string;
    evaluated_at: string;
  };
};

export function findingMarkup(finding: CandidateFinding): string {
  const evidence = finding.evidence;
  return `<aside class="finding" aria-label="Informational employment finding"><strong>Employment information</strong><p>${escapeText(finding.message)}</p><details><summary>Supporting evidence</summary><dl><dt>Company</dt><dd>${escapeText(evidence.company)}</dd><dt>Confirmed dates</dt><dd>${escapeText(evidence.confirmed_start_date)} to ${escapeText(evidence.confirmed_end_date)}</dd><dt>Calculated duration</dt><dd>${evidence.calculated_duration.calendar_months} months, ${evidence.calculated_duration.remaining_days} days</dd><dt>Calculation version</dt><dd>${escapeText(evidence.calculation_version)}</dd><dt>Evaluated</dt><dd>${escapeText(evidence.evaluated_at)}</dd></dl></details></aside>`;
}

export function escapeText(value: string): string {
  const node = document.createElement("div");
  node.textContent = value;
  return node.innerHTML;
}
