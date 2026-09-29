import pytest
from django.core.exceptions import PermissionDenied, ValidationError

from modules.candidate.models import ResumeAsset
from modules.candidate.resume_service import create_upload, record_parse_result, record_scan_result
from tests.factories import CandidateProfileFactory

pytestmark = pytest.mark.django_db


def upload(profile, **overrides):
    values = {
        "filename": "synthetic-resume.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1024,
        "sha256": "a" * 64,
    }
    values.update(overrides)
    return create_upload(identity=profile.identity, profile=profile, values=values)


def test_upload_is_quarantined_and_not_disclosable_before_clean_scan():
    resume = upload(CandidateProfileFactory())
    assert resume.quarantine_key and not resume.clean_key
    with pytest.raises(PermissionDenied):
        record_parse_result(resume=resume, suggestions=[])


@pytest.mark.parametrize(
    "overrides",
    [
        {"content_type": "text/plain"},
        {"size_bytes": 0},
        {"size_bytes": 10_485_761},
    ],
)
def test_invalid_resume_metadata_is_rejected(overrides):
    with pytest.raises(ValidationError):
        upload(CandidateProfileFactory(), **overrides)


def test_mime_mismatch_rejects_and_never_creates_clean_key():
    resume = upload(CandidateProfileFactory())
    record_scan_result(
        resume=resume,
        clean=True,
        detected_mime="application/msword",
        provider_reference="synthetic-scan",
    )
    assert resume.scan_status == ResumeAsset.ScanStatus.REJECTED
    assert resume.clean_key == ""


@pytest.mark.parametrize(
    "scan_values",
    [
        {"signature_valid": False, "observed_size": 1024},
        {"signature_valid": True, "observed_size": 2048},
    ],
)
def test_signature_or_observed_size_mismatch_is_rejected(scan_values):
    resume = upload(CandidateProfileFactory())
    record_scan_result(
        resume=resume,
        clean=True,
        detected_mime="application/pdf",
        provider_reference="synthetic-scan",
        **scan_values,
    )
    assert resume.scan_status == ResumeAsset.ScanStatus.REJECTED
    assert resume.clean_key == ""


def test_parse_failure_keeps_manual_entry_and_no_invented_suggestions():
    resume = upload(CandidateProfileFactory())
    record_scan_result(
        resume=resume,
        clean=True,
        detected_mime="application/pdf",
        provider_reference="synthetic-scan",
    )
    record_parse_result(resume=resume, suggestions=None, failed=True)
    assert resume.parse_status == ResumeAsset.ParseStatus.PARSE_FAILED
    assert not resume.facts.exists()


def test_only_source_backed_parser_suggestions_are_stored():
    resume = upload(CandidateProfileFactory())
    record_scan_result(
        resume=resume,
        clean=True,
        detected_mime="application/pdf",
        provider_reference="synthetic-scan",
    )
    record_parse_result(
        resume=resume,
        suggestions=[
            {"fact_type": "employment_start", "value": None, "confidence": 0.5, "source_spans": []},
            {
                "fact_type": "employment_type",
                "value": "PERMANENT",
                "confidence": 0.9,
                "source_spans": [
                    {"resume_id": str(resume.id), "start_offset": 2, "end_offset": 11}
                ],
            },
        ],
    )
    assert list(resume.facts.values_list("fact_type", flat=True)) == ["employment_type"]
