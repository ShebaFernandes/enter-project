from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.concurrency import require_if_match, strong_etag
from modules.operations.idempotency import execute
from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import authorize_opening

from .models import Opening
from .openings import create_opening, update_opening
from .serializers import OpeningCreateSerializer, OpeningPatchSerializer, OpeningSerializer


class OpeningCollectionView(APIView):
    def get(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        queryset = Opening.objects.filter(tenant_id=tenant_id).prefetch_related("hiring_team")
        membership = request.tenant_membership
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
        return Response(OpeningSerializer(opening).data)

    def patch(self, request, tenant_id, opening_id):
        opening = get_object_or_404(Opening, pk=opening_id, tenant_id=tenant_id)
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
