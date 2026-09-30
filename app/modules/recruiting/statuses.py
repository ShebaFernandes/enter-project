from __future__ import annotations

from .application_models import CandidateFacingStatus, InternalRecruitingStatus

STATUS_SUGGESTIONS: dict[str, str] = {
    InternalRecruitingStatus.SHORTLISTED: CandidateFacingStatus.SHORTLISTED,
    InternalRecruitingStatus.CONTACTED: CandidateFacingStatus.RECRUITER_INTERESTED,
    InternalRecruitingStatus.SCREENING: CandidateFacingStatus.RECRUITER_INTERESTED,
    InternalRecruitingStatus.INTERVIEWING: CandidateFacingStatus.INTERVIEW_REQUESTED,
    InternalRecruitingStatus.OFFERED: CandidateFacingStatus.OFFER_MADE,
    InternalRecruitingStatus.REJECTED: CandidateFacingStatus.NOT_SELECTED,
}


def candidate_status_suggestion(internal_status: str) -> str | None:
    if internal_status not in InternalRecruitingStatus.values:
        raise ValueError("Unsupported internal recruiting status.")
    return STATUS_SUGGESTIONS.get(internal_status)


def validate_not_relevant(
    *, internal_status: str, structured_reasons: list[str], explanatory_note: str | None
) -> None:
    if internal_status != InternalRecruitingStatus.NOT_RELEVANT:
        return
    if not [reason for reason in structured_reasons if reason.strip()] and not (
        explanatory_note and explanatory_note.strip()
    ):
        from django.core.exceptions import ValidationError

        raise ValidationError(
            {"structured_reasons": "Not relevant requires a structured reason or note."}
        )
