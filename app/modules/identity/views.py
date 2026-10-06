from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from modules.tenancy.context import effective_role

from .redirects import safe_candidate_return_to
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
    candidate_entry = request.query_params.get("platform") == "candidate"
    return_to = safe_candidate_return_to(request) if candidate_entry else ""
    if settings.LOCAL_SYNTHETIC_AUTH_ENABLED and settings.ENV.app_env in {"local", "test"}:
        from urllib.parse import urlencode

        from .local_auth import issue_local_candidate_bootstrap, issue_local_recruiter_bootstrap

        if candidate_entry:
            issued = issue_local_candidate_bootstrap()
            params = {"token": issued.token}
            if return_to:
                params["return_to"] = return_to
            else:
                params["profile"] = "1"
            response = redirect(
                f"/api/v1/__local__/synthetic-candidate-session?{urlencode(params)}"
            )
        else:
            recruiter_bootstrap = issue_local_recruiter_bootstrap()
            destination = "&view=results" if request.query_params.get("view") == "results" else ""
            response = redirect(
                f"/api/v1/__local__/synthetic-recruiter-session?token={recruiter_bootstrap.token}{destination}"
            )
        response["Cache-Control"] = "no-store, private"
        response["Referrer-Policy"] = "no-referrer"
        return response
    if return_to:
        request.session["candidate_return_to"] = return_to
    else:
        request.session.pop("candidate_return_to", None)
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
    destination = (
        "/"
        if workforce
        else request.session.pop("candidate_return_to", None) or "/candidate/profile/"
    )
    return redirect(destination)
