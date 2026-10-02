from __future__ import annotations

from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.concurrency import strong_etag
from modules.operations.idempotency import execute

from .models import ResumeAsset
from .resume_service import create_upload, quarantine_upload_grant
from .serializers import (
    CandidateProfilePatchSerializer,
    ResumeUploadSerializer,
    VisibilityChangeSerializer,
    resume_state_data,
)
from .services import profile_data, profile_for, publish_profile, update_profile
from .visibility import replace_visibility


class MergePatchJSONParser(JSONParser):
    media_type = "application/merge-patch+json"


class CandidateProfileView(APIView):
    parser_classes = [JSONParser, MergePatchJSONParser]

    def get(self, request):
        profile = profile_for(request.user)
        response = Response(profile_data(profile))
        response["ETag"] = strong_etag(profile.id, profile.version)
        return response

    def patch(self, request):
        profile_for(request.user)

        def operation():
            serializer = CandidateProfilePatchSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            profile = update_profile(
                identity=request.user,
                if_match=request.headers.get("If-Match"),
                values=dict(serializer.validated_data),
            )
            response = Response(profile_data(profile))
            response["ETag"] = strong_etag(profile.id, profile.version)
            return response

        return execute(request, operation)


class CandidatePublishView(APIView):
    def post(self, request):
        profile_for(request.user)

        def operation():
            profile = publish_profile(
                identity=request.user, if_match=request.headers.get("If-Match")
            )
            response = Response(profile_data(profile))
            response["ETag"] = strong_etag(profile.id, profile.version)
            return response

        return execute(request, operation)


class CandidateVisibilityView(APIView):
    def put(self, request):
        profile = profile_for(request.user)

        def operation():
            serializer = VisibilityChangeSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            rule = replace_visibility(
                identity=request.user,
                profile=profile,
                if_match=request.headers.get("If-Match"),
                values=dict(serializer.validated_data),
            )
            response = Response(
                {
                    "mode": rule.mode,
                    "approved_tenant_ids": rule.approved_tenant_ids,
                    "matching_preferences": rule.matching_preferences,
                    "version": rule.version,
                }
            )
            response["ETag"] = strong_etag(rule.profile_id, rule.profile.version)
            return response

        return execute(request, operation)


class ResumeUploadView(APIView):
    def post(self, request):
        profile = profile_for(request.user)

        def operation():
            serializer = ResumeUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            resume = create_upload(
                identity=request.user, profile=profile, values=dict(serializer.validated_data)
            )
            return Response(quarantine_upload_grant(resume), status=status.HTTP_201_CREATED)

        return execute(request, operation)


class ResumeStateView(APIView):
    def get(self, request, resume_id):
        profile = profile_for(request.user)
        resume = get_object_or_404(
            ResumeAsset.objects.prefetch_related("facts"), pk=resume_id, profile=profile
        )
        return Response(resume_state_data(resume))


@ensure_csrf_cookie
def candidate_profile_page(request):
    response = render(
        request,
        "candidate/profile.html",
        {
            "page_bootstrap": {
                "version": 1,
                "page": "candidate-profile",
                "requiresSession": True,
            }
        },
    )
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response
