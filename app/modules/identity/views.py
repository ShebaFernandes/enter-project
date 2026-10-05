from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from modules.tenancy.context import effective_role

from .services import (
    exchange_code,
    global_sign_out,
    link_identity_with_role,
    sign_in,
    start_login,
    validate_id_token,
)


@api_view(["GET"])
def session_view(request: HttpRequest) -> Response:
    role = effective_role(request)
    return Response(
        {
            "actor_id": str(request.user.pk),
            "role": role,
            "tenant_id": getattr(request, "tenant_id", None),
            "expires_at": request.session.get_expiry_date(),
        }
    )


@api_view(["DELETE"])
def sign_out_view(request: HttpRequest) -> Response:
    global_sign_out(request)
    return Response(status=204)


@api_view(["GET"])
@permission_classes([AllowAny])
def login_start_view(request: HttpRequest):
    if settings.LOCAL_SYNTHETIC_AUTH_ENABLED and settings.ENV.app_env in {"local", "test"}:
        from .local_auth import issue_local_recruiter_bootstrap

        issued = issue_local_recruiter_bootstrap()
        response = redirect(f"/api/v1/__local__/synthetic-recruiter-session?token={issued.token}")
        response["Cache-Control"] = "no-store, private"
        response["Referrer-Policy"] = "no-referrer"
        return response
    started = start_login()
    request.session["oidc_state"] = started.state
    request.session["oidc_nonce"] = started.nonce
    request.session["pkce_verifier"] = started.verifier
    return redirect(started.authorization_url)


@api_view(["GET"])
@permission_classes([AllowAny])
def callback_view(request: HttpRequest) -> Response | HttpResponseRedirect:
    if request.query_params.get("state") != request.session.pop("oidc_state", None):
        return Response({"title": "Identity response unavailable"}, status=400)
    code = request.query_params.get("code")
    verifier = request.session.pop("pkce_verifier", None)
    nonce = request.session.pop("oidc_nonce", None)
    if not code or not verifier or not nonce:
        return Response({"title": "Identity response unavailable"}, status=400)
    tokens = exchange_code(code, verifier)
    claims = validate_id_token(str(tokens["id_token"]), nonce)
    workforce = str(claims.get("custom:identity_type", "candidate")).casefold() == "workforce"
    identity = link_identity_with_role(claims, workforce=workforce)
    sign_in(
        request,
        identity,
        claims=claims,
        refresh_token=str(tokens.get("refresh_token", "")) or None,
        workforce=workforce,
    )
    return redirect("/")
