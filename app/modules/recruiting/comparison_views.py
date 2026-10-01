from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.tenancy.context import tenant_context
from modules.tenancy.models import TenantMembership
from modules.tenancy.rls import tenant_transaction

from .comparison import compare_candidates
from .views import StrictSerializer


class ComparisonRequestSerializer(StrictSerializer):
    candidate_ids = serializers.ListField(
        child=serializers.UUIDField(), min_length=2, max_length=10
    )
    context_type = serializers.ChoiceField(choices=["SEARCH", "OPENING", "SHORTLIST"])
    context_id = serializers.UUIDField()

    def validate_candidate_ids(self, values):
        if len(set(values)) != len(values):
            raise serializers.ValidationError("Candidate selections must be unique.")
        return values


class ComparisonView(APIView):
    def post(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            raise PermissionDenied("Comparison unavailable")
        if not request.headers.get("Idempotency-Key"):
            raise serializers.ValidationError({"Idempotency-Key": "This header is required."})
        serializer = ComparisonRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            compare_candidates(
                membership=request.tenant_membership,
                **serializer.validated_data,
            )
        )


def recruiter_comparison_page(request, tenant_id):
    if not request.user.is_authenticated:
        raise PermissionDenied("Comparison unavailable")
    token = tenant_context.set(tenant_id)
    try:
        with tenant_transaction():
            membership = TenantMembership.objects.filter(
                tenant_id=tenant_id,
                identity=request.user,
                status=TenantMembership.Status.ACTIVE,
                role__in=[
                    TenantMembership.Role.RECRUITER,
                    TenantMembership.Role.HIRING_MANAGER,
                ],
            ).first()
    finally:
        tenant_context.reset(token)
    if membership is None:
        raise PermissionDenied("Comparison unavailable")
    response = render(
        request,
        "recruiter/comparison.html",
        {
            "tenant_id": tenant_id,
            "role": membership.role,
        },
    )
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response
