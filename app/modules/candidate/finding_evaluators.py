from __future__ import annotations

import calendar
from datetime import date

from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event

from .models import CandidateFinding, EmploymentRecord

CALCULATION_VERSION = "short-tenure-v1"
TEMPORARY_TYPES = {
    "INTERNSHIP",
    "APPRENTICESHIP",
    "FIXED_TERM_CONTRACT",
    "CONSULTING",
    "SEASONAL",
    "OTHER_TEMPORARY",
}


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year, month = value.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _duration(start: date, end: date) -> tuple[int, int]:
    months = (end.year - start.year) * 12 + end.month - start.month
    if _add_months(start, months) > end:
        months -= 1
    anchor = _add_months(start, months)
    return months, (end - anchor).days


@transaction.atomic
def evaluate_employment_record(record: EmploymentRecord) -> CandidateFinding:
    now = timezone.now()
    result = "NOT_FOUND"
    if record.is_current:
        result = "NOT_FOUND"
    elif record.employment_type in TEMPORARY_TYPES:
        result = "EXCLUDED"
    elif (
        record.start_date_state != "CONFIRMED"
        or record.end_date_state != "CONFIRMED"
        or record.start_date_precision != "DAY"
        or record.end_date_precision != "DAY"
        or record.start_date is None
        or record.end_date is None
        or record.end_date < record.start_date
    ):
        result = "INSUFFICIENT_DATA"
    elif record.end_date < _add_months(record.start_date, 12):
        result = "FOUND"
    months, days = (
        _duration(record.start_date, record.end_date)
        if record.start_date and record.end_date and record.end_date >= record.start_date
        else (0, 0)
    )
    CandidateFinding.objects.filter(
        profile=record.profile,
        code="SHORT_TENURE",
        source_record_id=record.id,
        superseded_at__isnull=True,
    ).update(superseded_at=now)
    evidence = {
        "employment_record_id": str(record.id),
        "company": record.company,
        "confirmed_start_date": record.start_date.isoformat()
        if record.start_date_state == "CONFIRMED" and record.start_date
        else None,
        "confirmed_end_date": record.end_date.isoformat()
        if record.end_date_state == "CONFIRMED" and record.end_date
        else None,
        "calculated_duration": {"calendar_months": months, "remaining_days": days},
        "calculation_version": CALCULATION_VERSION,
        "evaluated_at": now.isoformat().replace("+00:00", "Z"),
    }
    finding = CandidateFinding.objects.create(
        profile=record.profile,
        code="SHORT_TENURE",
        severity="INFORMATIONAL",
        result=result,
        source_record_type="EMPLOYMENT_RECORD",
        source_record_id=record.id,
        source_record_version=record.version,
        evidence=evidence,
        message_key="candidate.finding.short_tenure",
        calculation_version=CALCULATION_VERSION,
        evaluated_at=now,
    )
    audit = record_audit_event(
        actor=record.profile.identity,
        action="CANDIDATE_FINDING_EVALUATED",
        target_type="candidate_finding",
        target_id=str(finding.id),
        purpose_code="RECRUITING_DISCOVERY",
        outcome="ALLOWED",
        metadata={
            "code": "SHORT_TENURE",
            "result": result,
            "source_record_id": str(record.id),
            "calculation_version": CALCULATION_VERSION,
        },
    )
    finding.audit_references = [str(audit.id)]
    finding.save(update_fields=["audit_references"])
    return finding
