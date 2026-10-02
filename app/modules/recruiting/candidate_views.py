from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.candidate.services import profile_for
from modules.communications import application_notifications
from modules.operations.concurrency import strong_etag
from modules.operations.idempotency import execute

from .application_models import CandidateFacingStatus, InternalRecruitingStatus
from .applications import (
    own_application,
    preview_candidate_status,
    publish_candidate_status,
    replace_notification_preferences,
    submit_application,
    withdraw_application,
)
from .candidate_progress import application_data, candidate_applications


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail("invalid", input=data)
        return data


class NotificationPreferencesSerializer(serializers.Serializer):
    email = StrictBooleanField()
    whatsapp = StrictBooleanField()


class ApplicationSubmitSerializer(serializers.Serializer):
    opening_id = serializers.UUIDField()
    resume_id = serializers.UUIDField()
    answers = serializers.DictField()
    consent_record_id = serializers.UUIDField()
    notification_preferences = NotificationPreferencesSerializer()


class WithdrawalSerializer(serializers.Serializer):
    candidate_status = serializers.ChoiceField(choices=[CandidateFacingStatus.WITHDRAWN])
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("Explicit confirmation is required.")
        return value


class StatusPreviewSerializer(serializers.Serializer):
    internal_status = serializers.ChoiceField(choices=InternalRecruitingStatus.choices)


class StatusPublicationSerializer(serializers.Serializer):
    preview_id = serializers.UUIDField()
    candidate_status = serializers.ChoiceField(choices=CandidateFacingStatus.choices)
    confirm = serializers.BooleanField()
    notify_channels = serializers.ListField(
        child=serializers.ChoiceField(choices=["EMAIL", "WHATSAPP"]), required=False
    )

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("Explicit confirmation is required.")
        return value


class CandidateApplicationCollectionView(APIView):
    def get(self, request):
        profile = profile_for(request.user)
        return Response(
            [application_data(item) for item in candidate_applications(profile=profile)]
        )

    def post(self, request):
        profile_for(request.user)

        def operation():
            serializer = ApplicationSubmitSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            application = submit_application(
                identity=request.user,
                values=dict(serializer.validated_data),
                request_key=request.headers["Idempotency-Key"],
            )
            response = Response(application_data(application), status=status.HTTP_201_CREATED)
            response["ETag"] = strong_etag(application.id, application.version)
            return response

        return execute(request, operation)


class CandidateApplicationDetailView(APIView):
    def get(self, request, application_id):
        application = own_application(identity=request.user, application_id=application_id)
        response = Response(application_data(application))
        response["ETag"] = strong_etag(application.id, application.version)
        return response


class CandidateApplicationWithdrawView(APIView):
    def post(self, request, application_id):
        profile_for(request.user)

        def operation():
            serializer = WithdrawalSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            application = withdraw_application(
                identity=request.user,
                application_id=application_id,
                if_match=request.headers.get("If-Match"),
                request_key=request.headers["Idempotency-Key"],
            )
            response = Response(application_data(application))
            response["ETag"] = strong_etag(application.id, application.version)
            return response

        return execute(request, operation)


class CandidateNotificationPreferencesView(APIView):
    def put(self, request, application_id):
        profile_for(request.user)

        def operation():
            serializer = NotificationPreferencesSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            application = replace_notification_preferences(
                identity=request.user,
                application_id=application_id,
                if_match=request.headers.get("If-Match"),
                values=dict(serializer.validated_data),
            )
            response = Response(application_data(application))
            response["ETag"] = strong_etag(application.id, application.version)
            return response

        return execute(request, operation)


class ApplicationStatusPreviewView(APIView):
    def post(self, request, tenant_id, application_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = StatusPreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preview = preview_candidate_status(
            membership=request.tenant_membership,
            application_id=application_id,
            internal_status=serializer.validated_data["internal_status"],
            if_match=request.headers.get("If-Match"),
        )
        response = Response(
            {
                "preview_id": str(preview.id),
                "internal_status": preview.internal_status,
                "suggested_candidate_status": preview.suggested_candidate_status,
                "notification_preview": None,
                "published": False,
                "expires_at": preview.expires_at,
            }
        )
        response["ETag"] = strong_etag(preview.application_id, preview.application_version)
        return response


class ApplicationStatusPublishView(APIView):
    def post(self, request, tenant_id, application_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)

        def operation():
            serializer = StatusPublicationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            values = serializer.validated_data
            application = publish_candidate_status(
                membership=request.tenant_membership,
                application_id=application_id,
                preview_id=values["preview_id"],
                candidate_status=values["candidate_status"],
                if_match=request.headers.get("If-Match"),
                request_key=request.headers["Idempotency-Key"],
            )
            channels = list(values.get("notify_channels", []))
            try:
                notifications = application_notifications.queue_application_status_notifications(
                    application=application,
                    channels=channels,
                    candidate_status=values["candidate_status"],
                    request_key=request.headers["Idempotency-Key"],
                )
            except Exception:
                notifications = application_notifications.safe_failed_projection(channels)
            response = Response(
                {"application": application_data(application), "notifications": notifications},
                status=status.HTTP_202_ACCEPTED,
            )
            response["ETag"] = strong_etag(application.id, application.version)
            return response

        return execute(request, operation)


@ensure_csrf_cookie
def public_application_page(request, opening_id):
    from .public_openings import application_publication_link, available_publications, public_reader

    with public_reader():
        if not available_publications().filter(pk=opening_id).exists():
            raise Http404("Role unavailable")
    page_bootstrap: dict[str, object] = {
        "version": 1,
        "page": "public-role",
        "requiresSession": False,
        "openingId": str(opening_id),
    }
    context: dict[str, object] = {
        "opening_id": opening_id,
        "page_bootstrap": page_bootstrap,
    }
    if request.user.is_authenticated:
        try:
            profile = profile_for(request.user, create=False)
            link = application_publication_link(opening_id)
            resume = profile.resumes.filter(
                is_current=True,
                scan_status="CLEAN",
                parse_status="READY",
                deleted_at__isnull=True,
            ).first()
            consent = next(
                (
                    item
                    for item in profile.consents.filter(
                        purpose="APPLICATION_SUBMISSION",
                        withdrawn_at__isnull=True,
                    )
                    if item.expires_at > timezone.now()
                    and link is not None
                    and item.audience_scope.get("opening_id") == str(link.opening_id)
                ),
                None,
            )
            context.update(
                {
                    "resume_id": resume.id if resume else "",
                    "consent_id": consent.id if consent else "",
                }
            )
            if resume:
                page_bootstrap["resumeId"] = str(resume.id)
            if consent:
                page_bootstrap["consentId"] = str(consent.id)
        except (PermissionDenied, ObjectDoesNotExist):
            pass
    response = render(request, "candidate/application.html", context)
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response


@ensure_csrf_cookie
def candidate_progress_page(request):
    response = render(
        request,
        "candidate/progress.html",
        {
            "page_bootstrap": {
                "version": 1,
                "page": "candidate-progress",
                "requiresSession": True,
            }
        },
    )
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response
