from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import boto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.audit.service import record_audit_event
from modules.operations.crypto import encrypt
from modules.operations.outbox import enqueue

from .models import CandidateProfile, ExtractedFact, ResumeAsset

SUPPORTED_MIME = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_SIZE = 10_485_760


def quarantine_upload_grant(resume: ResumeAsset) -> dict[str, object]:
    client_kwargs = {
        "service_name": "s3",
        "region_name": settings.AWS_REGION,
        "config": Config(signature_version="s3v4"),
    }
    if settings.S3_ENDPOINT_URL:
        client_kwargs.update(
            {
                "endpoint_url": settings.S3_ENDPOINT_URL,
                "aws_access_key_id": "test",
                # LocalStack accepts this documented non-secret test credential.
                "aws_secret_access_key": "test",  # nosec B105
            }
        )
    client = boto3.client(**client_kwargs)
    required_headers = {
        "Content-Type": resume.declared_mime,
        "x-amz-meta-sha256": resume.sha256,
    }
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.RESUME_QUARANTINE_BUCKET,
            "Key": resume.quarantine_key,
            "ContentType": resume.declared_mime,
            "Metadata": {"sha256": resume.sha256},
        },
        ExpiresIn=600,
        HttpMethod="PUT",
    )
    return {
        "resume_id": resume.id,
        "content_url": f"/api/v1/candidate/resumes/{resume.id}/content",
        "upload_url": upload_url,
        "required_headers": required_headers,
        "expires_at": resume.created_at + timedelta(minutes=10),
    }


@transaction.atomic
def create_upload(*, identity, profile: CandidateProfile, values: dict[str, object]) -> ResumeAsset:
    if profile.identity_id != identity.id:
        raise PermissionDenied("Resume unavailable")
    content_type = str(values["content_type"])
    size = int(str(values["size_bytes"]))
    if content_type not in SUPPORTED_MIME or not 1 <= size <= MAX_SIZE:
        raise ValidationError({"file": "Unsupported or oversized resume."})
    ResumeAsset.objects.filter(profile=profile, is_current=True, deleted_at__isnull=True).update(
        is_current=False
    )
    resume = ResumeAsset.objects.create(
        profile=profile,
        quarantine_key=f"quarantine/{profile.id}/{uuid.uuid4()}",
        original_filename_ciphertext=encrypt(str(values["filename"])),
        declared_mime=content_type,
        size_bytes=size,
        sha256=str(values["sha256"]),
        retention_until=timezone.now() + timedelta(days=365),
    )
    record_audit_event(
        actor=identity,
        action="RESUME_UPLOAD_CREATED",
        target_type="resume_asset",
        target_id=str(resume.id),
        outcome="ALLOWED",
        metadata={"declared_mime": content_type, "size_band": "UP_TO_10MB"},
    )
    return resume


@transaction.atomic
def record_scan_result(
    *,
    resume: ResumeAsset,
    clean: bool,
    detected_mime: str,
    provider_reference: str,
    signature_valid: bool = True,
    observed_size: int | None = None,
) -> ResumeAsset:
    if (
        detected_mime not in SUPPORTED_MIME
        or detected_mime != resume.declared_mime
        or not signature_valid
        or (observed_size is not None and observed_size != resume.size_bytes)
    ):
        clean = False
    resume.detected_mime = detected_mime
    resume.scan_provider_ref = provider_reference
    resume.scan_status = ResumeAsset.ScanStatus.CLEAN if clean else ResumeAsset.ScanStatus.REJECTED
    if clean:
        resume.clean_key = f"clean/{resume.profile_id}/{resume.id}"
        resume.parse_status = ResumeAsset.ParseStatus.PARSING
    else:
        resume.clean_key = ""
        resume.parse_status = ResumeAsset.ParseStatus.NOT_STARTED
    resume.version += 1
    resume.save()
    return resume


@transaction.atomic
def record_parse_result(
    *, resume: ResumeAsset, suggestions: list[dict[str, object]] | None, failed: bool = False
) -> ResumeAsset:
    if resume.scan_status != ResumeAsset.ScanStatus.CLEAN or not resume.clean_key:
        raise PermissionDenied("Resume content unavailable before a clean security scan")
    ExtractedFact.objects.filter(resume=resume).delete()
    if failed:
        resume.parse_status = ResumeAsset.ParseStatus.PARSE_FAILED
    else:
        # Phase 3 accepts only source-backed deterministic parser output. AI extraction is disabled.
        for suggestion in suggestions or []:
            if suggestion.get("value") is None or not suggestion.get("source_spans"):
                continue
            ExtractedFact.objects.create(
                resume=resume,
                fact_type=str(suggestion["fact_type"]),
                normalized_value=suggestion["value"],
                source_spans=suggestion["source_spans"],
                confidence=(
                    Decimal(str(suggestion["confidence"]))
                    if suggestion.get("confidence") is not None
                    else None
                ),
                extraction_method="DETERMINISTIC_PARSER",
            )
        resume.parse_status = ResumeAsset.ParseStatus.REVIEW_REQUIRED
    resume.version += 1
    resume.save(update_fields=("parse_status", "version"))
    return resume


def mark_review_ready(*, resume: ResumeAsset) -> ResumeAsset:
    if resume.scan_status != ResumeAsset.ScanStatus.CLEAN:
        raise PermissionDenied("Resume content unavailable")
    resume.parse_status = ResumeAsset.ParseStatus.READY
    resume.version += 1
    resume.save(update_fields=("parse_status", "version"))
    enqueue(
        aggregate_type="resume_asset",
        aggregate_id=resume.id,
        aggregate_version=resume.version,
        event_type="resume.extraction_ready.v1",
        payload={"resume_id": str(resume.id)},
        idempotency_key=f"resume-ready:{resume.id}:{resume.version}",
        actor_id=resume.profile.identity_id,
    )
    return resume
