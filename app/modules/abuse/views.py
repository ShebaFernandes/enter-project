from datetime import datetime

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.identity.models import IdentityCapability
from modules.identity.services import begin_step_up, complete_step_up, validate_id_token

from .policy import create_override


class StepUpChallengeView(APIView):
    def post(self, request):
        purpose = str(request.data.get("purpose", "")).strip()
        if not purpose:
            return Response({"title": "Purpose is required"}, status=422)
        nonce, purpose = begin_step_up(request, purpose=purpose)
        return Response(
            {
                "challenge": "REAUTHENTICATE",
                "nonce": nonce,
                "purpose": purpose,
                "permanent_lockout": False,
            },
            status=202,
        )

    def put(self, request):
        token = str(request.data.get("id_token", ""))
        nonce = str(request.data.get("nonce", ""))
        purpose = str(request.data.get("purpose", ""))
        if not token or not nonce or not purpose:
            return Response({"title": "Step-up response is incomplete"}, status=422)
        try:
            claims = validate_id_token(token, nonce)
            evidence = complete_step_up(
                request, claims=claims, expected_nonce=nonce, purpose=purpose
            )
        except PermissionDenied:
            return Response({"title": "Step-up verification unavailable"}, status=403)
        return Response({"evidence_id": str(evidence.id), "expires_at": evidence.expires_at})


class AbuseOverrideView(APIView):
    def post(self, request):
        is_security_admin = request.user.capabilities.filter(
            role=IdentityCapability.Role.PLATFORM_SECURITY_ADMIN,
            revoked_at__isnull=True,
        ).exists()
        if not is_security_admin:
            raise PermissionDenied("Operation unavailable")
        try:
            expires_at = datetime.fromisoformat(str(request.data["expires_at"]))
            if timezone.is_naive(expires_at):
                expires_at = timezone.make_aware(expires_at)
            override = create_override(
                subject_token=str(request.data["subject_token"]),
                action=str(request.data["action"]),
                reason_code=str(request.data["reason_code"]),
                approved_by=request.user,
                expires_at=expires_at,
            )
        except (KeyError, TypeError, ValueError):
            return Response({"title": "Override request is invalid"}, status=422)
        return Response({"id": str(override.id), "expires_at": override.expires_at}, status=201)
