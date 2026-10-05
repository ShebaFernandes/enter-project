import { useId, useState, type SyntheticEvent } from "react";
import { createPortal } from "react-dom";
import { fieldText } from "./candidate-detail";

type Employment = {
  company: string;
  role_title?: string;
  start_date: string | null;
  end_date: string | null;
  is_current?: boolean;
  employment_type?: string;
  provenance?: string;
  description?: string;
};
type Segment = { start: number; end: number; record?: Employment };
export function CareerJourney({ history }: { history: unknown }) {
  const id = useId();
  const [active, setActive] = useState<number | null>(null);
  const [tipPosition, setTipPosition] = useState({ left: 0, top: 0 });
  function show(index: number, event: SyntheticEvent<HTMLButtonElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    setTipPosition({
      left: Math.max(
        12,
        Math.min(window.innerWidth - 292, rect.left + rect.width / 2 - 140),
      ),
      top: rect.bottom + 8,
    });
    setActive(index);
  }
  const records = (Array.isArray(history) ? history : []).filter(
    (record): record is Employment =>
      !!record &&
      typeof record === "object" &&
      typeof record.company === "string",
  );
  const now = Date.now();
  const dated = records
    .map((record) => ({
      record,
      start: Date.parse(record.start_date ?? ""),
      end: record.is_current ? now : Date.parse(record.end_date ?? ""),
    }))
    .filter(
      (entry) =>
        Number.isFinite(entry.start) &&
        Number.isFinite(entry.end) &&
        entry.end >= entry.start,
    )
    .sort((a, b) => a.start - b.start);
  const segments: Segment[] = [];
  let previousEnd: number | null = null;
  for (const entry of dated) {
    if (previousEnd !== null && entry.start > previousEnd)
      segments.push({ start: previousEnd, end: entry.start });
    segments.push(entry);
    previousEnd = Math.max(previousEnd ?? entry.end, entry.end);
  }
  const start = dated[0]?.start ?? 0;
  const end = Math.max(...dated.map((entry) => entry.end), start + 1);
  const position = (date: number) => ((date - start) / (end - start)) * 100;
  const year = (date: number) => new Date(date).getUTCFullYear();
  const dateLabel = (record: Employment) =>
    `${record.start_date ?? "Unknown"} – ${record.is_current ? "Present" : (record.end_date ?? "Unknown")}`;
  return (
    <div className="result-timeline">
      <span className="career-journey-label">career journey</span>
      {dated.length ? (
        <div className="career-map" aria-label="Career journey">
          {segments.map((segment, index) => {
            const record = segment.record;
            const months = Math.max(
              1,
              Math.round((segment.end - segment.start) / (86400000 * 30.44)),
            );
            const gapDuration =
              months >= 12
                ? `${Number((months / 12).toFixed(1))} yr`
                : `${months} mo`;
            const label = record?.company ?? `${gapDuration} GAP`;
            return (
              <div key={index}>
                <span
                  className={record ? "career-map-line" : "career-map-gap"}
                  style={{
                    left: `${position(segment.start)}%`,
                    width: `${position(segment.end) - position(segment.start)}%`,
                  }}
                />
                <span
                  className="career-map-node"
                  style={{ left: `${position(segment.start)}%` }}
                />
                <span
                  className="career-map-node"
                  style={{ left: `${position(segment.end)}%` }}
                />
                <button
                  className={`career-map-label ${record ? "" : "career-map-gap-label"}`}
                  style={{
                    left: `${(position(segment.start) + position(segment.end)) / 2}%`,
                  }}
                  aria-describedby={
                    active === index ? `${id}-${index}` : undefined
                  }
                  onMouseEnter={(event) => show(index, event)}
                  onMouseLeave={() => setActive(null)}
                  onFocus={(event) => show(index, event)}
                  onBlur={() => setActive(null)}
                  onClick={(event) => show(index, event)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") setActive(null);
                  }}
                >
                  {label}
                </button>
                {active === index &&
                  createPortal(
                    <div
                      role="tooltip"
                      id={`${id}-${index}`}
                      className="career-tooltip"
                      style={tipPosition}
                    >
                      <strong>
                        {record
                          ? `${fieldText(record.role_title)} at ${record.company}`
                          : "Career gap"}
                      </strong>
                      <ul>
                        <li>
                          {record
                            ? dateLabel(record)
                            : `${new Date(segment.start).toISOString().slice(0, 10)} – ${new Date(segment.end).toISOString().slice(0, 10)}`}
                        </li>
                        {record?.description && <li>{record.description}</li>}
                        {record?.employment_type && (
                          <li>{record.employment_type.replaceAll("_", " ")}</li>
                        )}
                      </ul>
                    </div>,
                    document.querySelector(".enter-ui") ?? document.body,
                  )}
                <span
                  className="career-map-year"
                  style={{ left: `${position(segment.start)}%` }}
                >
                  {year(segment.start)}
                </span>
              </div>
            );
          })}
          <span className="career-map-year end">
            {dated.some((entry) => entry.record.is_current) ? "Now" : year(end)}
          </span>
        </div>
      ) : (
        <span className="career-unavailable">Employment dates unavailable</span>
      )}
      {!dated.length && records.length > 0 && (
        <div className="career-undated">
          {records.map((record, index) => (
            <span
              key={index}
              title={`${fieldText(record.role_title)} · ${dateLabel(record)}`}
            >
              {record.company}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
