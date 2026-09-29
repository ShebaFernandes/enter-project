from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlparse

from rest_framework import serializers

from .models import EmploymentRecord, ResumeAsset, VisibilityRule


class EmploymentRecordInputSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    company = serializers.CharField(min_length=1, max_length=300, trim_whitespace=True)
    role_title = serializers.CharField(
        max_length=300, required=False, allow_blank=True, allow_null=True
    )
    start_date = serializers.DateField(required=True, allow_null=True)
    end_date = serializers.DateField(required=True, allow_null=True)
    start_date_state = serializers.ChoiceField(choices=EmploymentRecord.ValueState.choices)
    end_date_state = serializers.ChoiceField(choices=EmploymentRecord.ValueState.choices)
    is_current = serializers.BooleanField()
    employment_type = serializers.ChoiceField(choices=EmploymentRecord.EmploymentType.choices)
    employment_type_state = serializers.ChoiceField(choices=EmploymentRecord.ValueState.choices)
    provenance = serializers.ChoiceField(choices=EmploymentRecord.Provenance.choices)
    confidence = serializers.DecimalField(
        max_digits=4,
        decimal_places=3,
        min_value=Decimal("0"),
        max_value=Decimal("1"),
        required=False,
        allow_null=True,
    )
    source_spans = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, attrs):
        if attrs["is_current"] and attrs["end_date"] is not None:
            raise serializers.ValidationError(
                {"end_date": "A current role cannot have an end date."}
            )
        if attrs["is_current"] and attrs["end_date_state"] == EmploymentRecord.ValueState.CONFIRMED:
            raise serializers.ValidationError(
                {"end_date_state": "A current role cannot have a confirmed end date."}
            )
        if (
            attrs["start_date_state"] == EmploymentRecord.ValueState.CONFIRMED
            and attrs["start_date"] is None
        ):
            raise serializers.ValidationError({"start_date": "A confirmed date requires a value."})
        if (
            attrs["end_date_state"] == EmploymentRecord.ValueState.CONFIRMED
            and attrs["end_date"] is None
        ):
            raise serializers.ValidationError({"end_date": "A confirmed date requires a value."})
        if attrs["start_date"] and attrs["end_date"] and attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError({"end_date": "End date cannot precede start date."})
        for span in attrs.get("source_spans", []):
            allowed = {"resume_id", "page", "start_offset", "end_offset"}
            if set(span) - allowed or not {"resume_id", "start_offset", "end_offset"} <= set(span):
                raise serializers.ValidationError({"source_spans": "Source spans are malformed."})
        return attrs


class CandidateProfilePatchSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=200, required=False, allow_blank=False)
    location = serializers.DictField(required=False)
    headline = serializers.CharField(
        max_length=300, required=False, allow_blank=True, allow_null=True
    )
    current_role = serializers.CharField(
        max_length=200, required=False, allow_blank=True, allow_null=True
    )
    current_company = serializers.CharField(
        max_length=200, required=False, allow_blank=True, allow_null=True
    )
    experience_years = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), required=False
    )
    skills = serializers.ListField(
        child=serializers.CharField(min_length=1, max_length=200), min_length=1, required=False
    )
    employment_history = EmploymentRecordInputSerializer(many=True, required=False)
    role_categories = serializers.ListField(
        child=serializers.CharField(max_length=200), required=False
    )
    preferred_locations = serializers.ListField(
        child=serializers.CharField(max_length=200), required=False
    )
    work_arrangements = serializers.ListField(
        child=serializers.ChoiceField(choices=["FLEXIBLE", "REMOTE", "HYBRID", "ON_SITE"]),
        required=False,
    )
    meaningful_work = serializers.CharField(
        max_length=300, required=False, allow_blank=True, allow_null=True
    )
    notice_period = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True
    )
    availability_date = serializers.DateField(required=False, allow_null=True)
    compensation = serializers.DictField(required=False, allow_null=True)
    professional_links = serializers.ListField(
        child=serializers.URLField(max_length=500), required=False
    )
    contact_preferences = serializers.DictField(required=False)

    def validate_compensation(self, value):
        if value is None:
            return value
        if set(value) != {"currency", "amount_minor", "period"}:
            raise serializers.ValidationError("Currency, amount_minor, and period are required.")
        if (
            not isinstance(value["currency"], str)
            or len(value["currency"]) != 3
            or not value["currency"].isupper()
        ):
            raise serializers.ValidationError("Currency must be a three-letter uppercase code.")
        if not isinstance(value["amount_minor"], int) or value["amount_minor"] < 0:
            raise serializers.ValidationError(
                "Amount must be a nonnegative integer in minor units."
            )
        if value["period"] not in {"HOUR", "DAY", "MONTH", "YEAR"}:
            raise serializers.ValidationError("Compensation period is invalid.")
        return value

    def validate_professional_links(self, values):
        for value in values:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise serializers.ValidationError("Only safe HTTP(S) links are accepted.")
        return values


class VisibilityChangeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=VisibilityRule.Mode.choices)
    consent_record_id = serializers.UUIDField()
    approved_tenant_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=False
    )
    matching_preferences = serializers.DictField(required=False, allow_empty=False)

    def validate(self, attrs):
        mode = attrs["mode"]
        allowed = {"mode", "consent_record_id"}
        if mode == VisibilityRule.Mode.APPROVED_RECRUITERS:
            allowed.add("approved_tenant_ids")
            if not attrs.get("approved_tenant_ids"):
                raise serializers.ValidationError(
                    {"approved_tenant_ids": "An explicit recruiter audience is required."}
                )
        elif mode == VisibilityRule.Mode.MATCHING_ROLES:
            allowed.add("matching_preferences")
            if not attrs.get("matching_preferences"):
                raise serializers.ValidationError(
                    {"matching_preferences": "Deterministic matching preferences are required."}
                )
        unknown = set(self.initial_data) - allowed
        if unknown:
            raise serializers.ValidationError(
                {key: "This field is not permitted." for key in unknown}
            )
        return attrs


class ResumeUploadSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.ChoiceField(
        choices=[
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]
    )
    size_bytes = serializers.IntegerField(min_value=1, max_value=10_485_760)
    sha256 = serializers.RegexField(r"^[a-f0-9]{64}$")


def employment_record_data(record: EmploymentRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "company": record.company,
        "role_title": record.role_title or None,
        "start_date": record.start_date,
        "end_date": record.end_date,
        "start_date_state": record.start_date_state,
        "end_date_state": record.end_date_state,
        "is_current": record.is_current,
        "employment_type": record.employment_type,
        "employment_type_state": record.employment_type_state,
        "provenance": record.provenance,
        "confidence": record.confidence,
        "source_spans": record.source_spans,
        "version": record.version,
    }


def resume_state_data(resume: ResumeAsset) -> dict[str, object]:
    return {
        "id": resume.id,
        "scan_status": resume.scan_status,
        "parse_status": resume.parse_status,
        "manual_entry_available": resume.parse_status == ResumeAsset.ParseStatus.PARSE_FAILED,
        "suggestions": [
            {
                "id": fact.id,
                "fact_type": fact.fact_type,
                "value": fact.normalized_value,
                "confidence": fact.confidence,
                "source_spans": fact.source_spans,
                "state": fact.state,
            }
            for fact in resume.facts.all()
        ],
    }
