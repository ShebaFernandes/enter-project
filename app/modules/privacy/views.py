from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.candidate.services import profile_for
from modules.identity.services import require_recent_step_up
from modules.operations.idempotency import execute

from .export_service import download_export
from .models import DataRightsRequest
from .serializers import EscalationSerializer, RightsRequestCreateSerializer
from .services import create_rights_request, escalate, rights_request_data


class RightsRequestCollectionView(APIView):
    def get(self, request):
        profile = profile_for(request.user)
        items = profile.rights_requests.order_by("-submitted_at")
        return Response([rights_request_data(item) for item in items])

    def post(self, request):
        profile = profile_for(request.user)

        def operation():
            serializer = RightsRequestCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            values = dict(serializer.validated_data)
            evidence = None
            if values["request_type"] == DataRightsRequest.RequestType.DELETE:
                evidence = require_recent_step_up(request, purpose="candidate-deletion")
                if str(evidence.id) != str(values.pop("step_up_proof")):
                    raise PermissionDenied("Step-up proof unavailable")
            item = create_rights_request(
                identity=request.user,
                profile=profile,
                values=values,
                step_up_evidence=evidence,
            )
            return Response(rights_request_data(item), status=status.HTTP_202_ACCEPTED)

        return execute(request, operation)


class RightsRequestDetailView(APIView):
    def get(self, request, rights_request_id):
        profile = profile_for(request.user)
        item = get_object_or_404(DataRightsRequest, pk=rights_request_id, profile=profile)
        return Response(rights_request_data(item))


class RightsExportDownloadView(APIView):
    def post(self, request, rights_request_id):
        profile = profile_for(request.user)
        item = get_object_or_404(DataRightsRequest, pk=rights_request_id, profile=profile)

        def operation():
            return Response(download_export(identity=request.user, request=item))

        return execute(request, operation)


class RightsEscalationView(APIView):
    def post(self, request, rights_request_id):
        profile = profile_for(request.user)
        item = get_object_or_404(DataRightsRequest, pk=rights_request_id, profile=profile)

        def operation():
            serializer = EscalationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            escalate(identity=request.user, item=item, reason=serializer.validated_data["reason"])
            return Response(status=status.HTTP_202_ACCEPTED)

        return execute(request, operation)


@ensure_csrf_cookie
def rights_center_page(request):
    response = render(
        request,
        "candidate/rights-center.html",
        {
            "page_bootstrap": {
                "version": 1,
                "page": "candidate-rights",
                "requiresSession": True,
            }
        },
    )
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response
