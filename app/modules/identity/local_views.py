from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from .local_auth import (
    consume_local_candidate_bootstrap,
    consume_local_recruiter_bootstrap,
    consume_local_tenant_admin_bootstrap,
)
from .services import sign_in


@api_view(["GET"])
@permission_classes([AllowAny])
def local_recruiter_session_view(request: HttpRequest) -> HttpResponse:
    try:
        identity, membership = consume_local_recruiter_bootstrap(
            str(request.query_params.get("token", ""))
        )
    except PermissionDenied as exc:
        raise Http404("Synthetic session unavailable") from exc
    sign_in(
        request,
        identity,
        claims={
            "email_verified": True,
            "amr": ["mfa"],
            "origin_jti": "local-synthetic-session",
            "identities": "LOCAL_SYNTHETIC",
        },
        workforce=True,
    )
    response = HttpResponseRedirect(f"/tenants/{membership.tenant_id}/recruiter/search/")
    response["Cache-Control"] = "no-store, private"
    response["Referrer-Policy"] = "no-referrer"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def local_candidate_session_view(request: HttpRequest) -> HttpResponse:
    try:
        identity, opening = consume_local_candidate_bootstrap(
            str(request.query_params.get("token", ""))
        )
    except PermissionDenied as exc:
        raise Http404("Synthetic session unavailable") from exc
    sign_in(
        request,
        identity,
        claims={
            "email_verified": True,
            "amr": ["email"],
            "origin_jti": "local-synthetic-candidate-session",
            "identities": "LOCAL_SYNTHETIC",
        },
        workforce=False,
    )
    response = HttpResponseRedirect(f"/roles/{opening.openingpublicationlink.public_id}/")
    response["Cache-Control"] = "no-store, private"
    response["Referrer-Policy"] = "no-referrer"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def local_tenant_admin_session_view(request: HttpRequest) -> HttpResponse:
    try:
        identity, membership = consume_local_tenant_admin_bootstrap(
            str(request.query_params.get("token", ""))
        )
    except PermissionDenied as exc:
        raise Http404("Synthetic session unavailable") from exc
    sign_in(
        request,
        identity,
        claims={
            "email_verified": True,
            "amr": ["mfa"],
            "origin_jti": "local-synthetic-tenant-admin-session",
            "identities": "LOCAL_SYNTHETIC",
        },
        workforce=True,
    )
    response = HttpResponseRedirect(f"/tenants/{membership.tenant_id}/admin/governance/")
    response["Cache-Control"] = "no-store, private"
    response["Referrer-Policy"] = "no-referrer"
    return response
