import uuid

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.concurrency import require_if_match, strong_etag
from modules.operations.idempotency import IdempotencyConflict, complete, execute, reserve
from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import authorize_opening

from .applicant_review import applications_for_opening
from .models import Opening
from .openings import create_opening, delete_opening, update_opening
from .public_openings import (
    authorized_publication_opening,
    publication_preview,
    synchronize_publication,
)
from .recruiter_entered import (
    create_recruiter_entered_candidate,
    list_recruiter_entered_candidates,
)
from .serializers import (
    OpeningCreateSerializer,
    OpeningPatchSerializer,
    OpeningSerializer,
    RecruiterEnteredCandidateCreateSerializer,
    RecruiterEnteredCandidateSerializer,
)

LOCAL_SYNTHETIC_BASE_OPENING_ID = uuid.UUID("00000000-0000-4000-8000-000000000106")


class OpeningCollectionView(APIView):
    def get(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        queryset = (
            Opening.objects.filter(tenant_id=tenant_id)
            .prefetch_related("hiring_team")
            .order_by("-created_at", "-id")
        )
        membership = request.tenant_membership
        if (
            settings.LOCAL_SYNTHETIC_AUTH_ENABLED
            and membership.role == TenantMembership.Role.TENANT_ADMIN
        ):
            queryset = queryset.exclude(pk=LOCAL_SYNTHETIC_BASE_OPENING_ID)
        if membership.role == TenantMembership.Role.HIRING_MANAGER:
            queryset = queryset.filter(hiring_team__membership=membership)
        if membership.scope.get("opening_ids"):
            queryset = queryset.filter(id__in=membership.scope["opening_ids"])
        if membership.scope.get("business_unit_ids"):
            queryset = queryset.filter(business_unit_id__in=membership.scope["business_unit_ids"])
        return Response(OpeningSerializer(queryset.distinct(), many=True).data)

    def post(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)

        def operation():
            serializer = OpeningCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            values = dict(serializer.validated_data)
            team = values.pop("hiring_team_ids", ())
            opening = create_opening(
                membership=request.tenant_membership, hiring_team_ids=team, **values
            )
            return Response(OpeningSerializer(opening).data, status=status.HTTP_201_CREATED)

        return execute(request, operation)


class OpeningDetailView(APIView):
    def get(self, request, tenant_id, opening_id):
        opening = get_object_or_404(
            Opening.objects.prefetch_related("hiring_team"), pk=opening_id, tenant_id=tenant_id
        )
        authorize_opening(request.tenant_membership, opening, "opening.read")
        response = Response(OpeningSerializer(opening).data)
        response["ETag"] = strong_etag(opening.pk, opening.version)
        return response

    @transaction.atomic
    def patch(self, request, tenant_id, opening_id):
        opening = get_object_or_404(
            Opening.objects.select_for_update(), pk=opening_id, tenant_id=tenant_id
        )
        authorize_opening(request.tenant_membership, opening, "opening.write")
        require_if_match(request.headers.get("If-Match"), opening, request.data)
        serializer = OpeningPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        team = changes.pop("hiring_team_ids", None)
        opening = update_opening(
            opening=opening,
            membership=request.tenant_membership,
            changes=changes,
            hiring_team_ids=team,
        )
        response = Response(OpeningSerializer(opening).data)
        response["ETag"] = strong_etag(opening.pk, opening.version)
        return response

    @transaction.atomic
    def delete(self, request, tenant_id, opening_id):
        opening = get_object_or_404(
            Opening.objects.select_for_update(), pk=opening_id, tenant_id=tenant_id
        )
        authorize_opening(request.tenant_membership, opening, "opening.write")
        require_if_match(request.headers.get("If-Match"), opening, {})
        delete_opening(opening=opening, membership=request.tenant_membership)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OpeningApplicationCollectionView(APIView):
    def get(self, request, tenant_id, opening_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        opening = get_object_or_404(Opening, pk=opening_id, tenant_id=tenant_id)
        return Response(
            applications_for_opening(membership=request.tenant_membership, opening=opening)
        )


class OpeningPublicationView(APIView):
    """Authenticated tenant-scoped management, never a public source-table read."""

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    @transaction.atomic
    def get(self, request, tenant_id, opening_id, action=None):
        if action is not None:
            return Response(status=405)
        if request.tenant_id != tenant_id or request.tenant_membership is None:
            return Response(status=404)
        opening = get_object_or_404(Opening, pk=opening_id, tenant_id=tenant_id)
        opening, _ = authorized_publication_opening(
            opening=opening, membership=request.tenant_membership
        )
        data = publication_preview(opening)
        return Response(data, headers={"ETag": data["source_etag"], "Cache-Control": "no-store"})

    @transaction.atomic
    def post(self, request, tenant_id, opening_id, action=None):
        if action not in {"publish", "withdraw"}:
            return Response(status=405)
        if request.tenant_id != tenant_id or request.tenant_membership is None:
            return Response(status=404)
        opening = get_object_or_404(Opening, pk=opening_id, tenant_id=tenant_id)
        opening, membership = authorized_publication_opening(
            opening=opening, membership=request.tenant_membership
        )
        allowed = {"confirmed", "preview_digest"} if action == "publish" else {"confirmed"}
        if (
            not isinstance(request.data, dict)
            or set(request.data) - allowed
            or request.data.get("confirmed") is not True
        ):
            raise ValidationError(
                {"confirmed": "Explicit confirmation and approved fields are required."}
            )
        key = request.headers.get("Idempotency-Key", "")
        if not 16 <= len(key) <= 200:
            raise ValidationError({"Idempotency-Key": "A 16-200 character key is required."})
        # Scope existing persistence by actor/tenant/object/action. Revalidate
        # authorization above even when replaying a previously successful request.
        record, created = reserve(
            f"{request.user.pk}:{tenant_id}:{opening_id}:{action}",
            key,
            {"body": request.data, "if_match": request.headers.get("If-Match")},
        )
        if not created:
            if record.response_status is None:
                raise IdempotencyConflict("Publication request is pending")
            return Response(
                record.response_body,
                status=record.response_status,
                headers={"Cache-Control": "no-store"},
            )
        data = synchronize_publication(
            opening=opening,
            membership=membership,
            if_match=request.headers.get("If-Match"),
            confirmed=request.data.get("confirmed"),
            preview_digest=request.data.get("preview_digest", ""),
            withdraw=action == "withdraw",
        )
        complete(record, 200, data)
        return Response(data, headers={"ETag": data["source_etag"], "Cache-Control": "no-store"})


class RecruiterEnteredCandidateCollectionView(APIView):
    def get(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        candidates = list_recruiter_entered_candidates(membership=request.tenant_membership)
        return Response(RecruiterEnteredCandidateSerializer(candidates, many=True).data)

    def post(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)

        def operation():
            serializer = RecruiterEnteredCandidateCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            candidate = create_recruiter_entered_candidate(
                membership=request.tenant_membership,
                actor=request.user,
                values=dict(serializer.validated_data),
            )
            return Response(
                RecruiterEnteredCandidateSerializer(candidate).data,
                status=status.HTTP_201_CREATED,
            )

        return execute(request, operation)
