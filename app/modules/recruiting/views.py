from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.concurrency import strong_etag
from modules.operations.idempotency import execute

from .application_models import Application, InternalRecruitingStatus
from .candidate_work import (
    candidate_work_data,
    create_or_reuse_candidate_work,
    get_candidate_work,
)
from .disclosures import confirm_disclosure, disclosure_data, preview_disclosure
from .notes import create_note, list_notes, note_data
from .status_service import update_application_internal_status, update_candidate_work


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {key: "This field is not permitted." for key in unknown}
            )
        return super().to_internal_value(data)


class CandidateWorkCreateSerializer(StrictSerializer):
    candidate_id = serializers.UUIDField()
    originating_search_id = serializers.UUIDField()
    opening_id = serializers.UUIDField(required=False, allow_null=True)
    trigger = serializers.ChoiceField(choices=["VIEW", "NOTE", "SHORTLIST", "STATUS_CHANGE"])


class CandidateWorkUpdateSerializer(StrictSerializer):
    internal_status = serializers.ChoiceField(
        choices=InternalRecruitingStatus.choices, required=False
    )
    shortlisted = serializers.BooleanField(required=False)
    structured_reasons = serializers.ListField(
        child=serializers.CharField(max_length=200), required=False
    )
    explanatory_note = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one change is required.")
        return attrs


class NoteSerializer(StrictSerializer):
    body = serializers.CharField(min_length=1, max_length=5000, trim_whitespace=True)
    hiring_team_visible = serializers.BooleanField(required=False, default=False)


class InternalStatusSerializer(StrictSerializer):
    internal_status = serializers.ChoiceField(choices=InternalRecruitingStatus.choices)
    structured_reasons = serializers.ListField(
        child=serializers.CharField(max_length=200), required=False, default=list
    )
    explanatory_note = serializers.CharField(
        max_length=2000, required=False, allow_blank=True, allow_null=True
    )


class DestinationSerializer(StrictSerializer):
    type = serializers.ChoiceField(choices=["CANDIDATE_EMAIL", "CANDIDATE_WHATSAPP", "HIRING_TEAM"])
    identifier = serializers.CharField(min_length=1, max_length=500)
    label = serializers.CharField(  # type: ignore[assignment]
        max_length=200, required=False, allow_blank=True
    )


class DisclosurePreviewSerializer(StrictSerializer):
    context_type = serializers.ChoiceField(choices=["APPLICATION", "CANDIDATE_WORK"])
    context_id = serializers.UUIDField()
    purpose = serializers.ChoiceField(choices=["CANDIDATE_CONTACT", "HIRING_TEAM_SHARE"])
    destination = DestinationSerializer()
    requested_fields = serializers.ListField(
        child=serializers.CharField(max_length=100), min_length=1
    )


class DisclosureConfirmSerializer(StrictSerializer):
    preview_id = serializers.UUIDField()
    preview_hash = serializers.CharField(min_length=64, max_length=64)
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("Explicit confirmation is required.")
        return value


class CandidateWorkCollectionView(APIView):
    def post(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Candidate work unavailable")

        def operation():
            serializer = CandidateWorkCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            record, created = create_or_reuse_candidate_work(
                membership=request.tenant_membership, **serializer.validated_data
            )
            response = Response(
                candidate_work_data(record),
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
            response["ETag"] = strong_etag(record.id, record.version)
            return response

        return execute(request, operation)


class CandidateWorkDetailView(APIView):
    def get(self, request, tenant_id, candidate_work_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Candidate work unavailable")
        record = get_candidate_work(
            membership=request.tenant_membership, candidate_work_id=candidate_work_id
        )
        response = Response(candidate_work_data(record))
        response["ETag"] = strong_etag(record.id, record.version)
        return response

    def patch(self, request, tenant_id, candidate_work_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Candidate work unavailable")

        def operation():
            serializer = CandidateWorkUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            record = get_candidate_work(
                membership=request.tenant_membership, candidate_work_id=candidate_work_id
            )
            updated = update_candidate_work(
                membership=request.tenant_membership,
                record=record,
                if_match=request.headers.get("If-Match"),
                request_key=request.headers["Idempotency-Key"],
                **serializer.validated_data,
            )
            response = Response(candidate_work_data(updated))
            response["ETag"] = strong_etag(updated.id, updated.version)
            return response

        return execute(request, operation)


class _NoteCollectionView(APIView):
    context_type = ""

    def _context(self, request, context_id):
        if self.context_type == "CANDIDATE_WORK":
            return {
                "candidate_work": get_candidate_work(
                    membership=request.tenant_membership, candidate_work_id=context_id
                )
            }
        return {
            "application": get_object_or_404(
                Application.objects.select_related("opening"),
                pk=context_id,
                tenant_id=request.tenant_id,
            )
        }

    def get(self, request, tenant_id, context_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Notes unavailable")
        context = self._context(request, context_id)
        return Response(
            [
                note_data(note)
                for note in list_notes(membership=request.tenant_membership, **context)
            ]
        )

    def post(self, request, tenant_id, context_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Notes unavailable")

        def operation():
            serializer = NoteSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            context = self._context(request, context_id)
            note = create_note(
                membership=request.tenant_membership,
                **context,
                **serializer.validated_data,
            )
            response = Response(note_data(note), status=status.HTTP_201_CREATED)
            response["ETag"] = strong_etag(note.id, note.version)
            return response

        return execute(request, operation)


class CandidateWorkNoteCollectionView(_NoteCollectionView):
    context_type = "CANDIDATE_WORK"


class ApplicationNoteCollectionView(_NoteCollectionView):
    context_type = "APPLICATION"


class ApplicationInternalStatusView(APIView):
    def put(self, request, tenant_id, application_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Application unavailable")

        def operation():
            serializer = InternalStatusSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            application = update_application_internal_status(
                membership=request.tenant_membership,
                application_id=application_id,
                if_match=request.headers.get("If-Match"),
                request_key=request.headers["Idempotency-Key"],
                **serializer.validated_data,
            )
            response = Response(
                {
                    "id": str(application.id),
                    "internal_status": application.internal_status,
                    "suggested_candidate_status": application.suggested_candidate_status,
                    "candidate_status": application.candidate_status,
                    "version": application.version,
                }
            )
            response["ETag"] = strong_etag(application.id, application.version)
            return response

        return execute(request, operation)


class DisclosurePreviewView(APIView):
    def post(self, request, tenant_id, candidate_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Disclosure unavailable")

        def operation():
            serializer = DisclosurePreviewSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            disclosure = preview_disclosure(
                membership=request.tenant_membership,
                candidate_id=candidate_id,
                values=dict(serializer.validated_data),
                request_key=request.headers["Idempotency-Key"],
            )
            return Response(disclosure_data(disclosure))

        return execute(request, operation)


class DisclosureConfirmView(APIView):
    def post(self, request, tenant_id, candidate_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Disclosure unavailable")

        def operation():
            serializer = DisclosureConfirmSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
            disclosure = confirm_disclosure(
                membership=request.tenant_membership,
                candidate_id=candidate_id,
                preview_id=values["preview_id"],
                preview_hash=values["preview_hash"],
                request_key=request.headers["Idempotency-Key"],
            )
            return Response(disclosure_data(disclosure), status=status.HTTP_202_ACCEPTED)

        return execute(request, operation)


@ensure_csrf_cookie
def recruiter_candidate_page(request, tenant_id, candidate_id):
    from modules.tenancy.models import TenantMembership
    from modules.tenancy.page_views import _membership

    if request.tenant_id is not None and request.tenant_id != tenant_id:
        raise PermissionDenied("Candidate unavailable")
    membership = _membership(
        request,
        tenant_id,
        [TenantMembership.Role.RECRUITER, TenantMembership.Role.HIRING_MANAGER],
    )
    response = render(
        request,
        "recruiter/candidate-detail.html",
        {"tenant_id": membership.tenant_id, "candidate_id": candidate_id},
    )
    response["Cache-Control"] = "no-store, private"
    return response
