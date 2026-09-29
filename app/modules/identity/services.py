from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import jwt
from django.conf import settings
from django.contrib.auth import login, logout
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from modules.operations.crypto import blind_index, encrypt

from .models import Identity


@dataclass(frozen=True)
class LoginStart:
    authorization_url: str
    state: str
    nonce: str
    verifier: str


def start_login() -> LoginStart:
    state, nonce, verifier = (
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(64),
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    params = {
        "client_id": settings.ENV.cognito_client_id,
        "response_type": "code",
        "scope": "openid email",
        "redirect_uri": settings.ENV.cognito_callback_url,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return LoginStart(
        f"{settings.ENV.cognito_issuer.rstrip('/')}/oauth2/authorize?{urlencode(params)}",
        state,
        nonce,
        verifier,
    )


def exchange_code(code: str, verifier: str) -> dict[str, object]:
    if settings.ENV.app_env in {"local", "test"}:
        raise PermissionDenied("External identity exchange is unavailable in local/test mode")
    response = httpx.post(
        f"{settings.ENV.cognito_issuer.rstrip('/')}/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.ENV.cognito_client_id,
            "client_secret": settings.ENV.cognito_client_secret,
            "code": code,
            "redirect_uri": settings.ENV.cognito_callback_url,
            "code_verifier": verifier,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def validate_id_token(token: str, expected_nonce: str) -> dict[str, object]:
    jwks = jwt.PyJWKClient(f"{settings.ENV.cognito_issuer.rstrip('/')}/.well-known/jwks.json")
    signing_key = jwks.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.ENV.cognito_client_id,
        issuer=settings.ENV.cognito_issuer,
    )
    if claims.get("nonce") != expected_nonce:
        raise PermissionDenied("Identity response unavailable")
    return claims


def link_verified_identity(claims: dict[str, object]) -> Identity:
    subject = str(claims.get("sub", ""))
    email = str(claims.get("email", ""))
    if not subject or not email or claims.get("email_verified") is not True:
        raise PermissionDenied("Verified identity required")
    identity, _ = Identity.objects.update_or_create(
        cognito_subject=subject,
        defaults={
            "email_lookup_hmac": blind_index(email, purpose="verified-email"),
            "email_ciphertext": encrypt(email),
            "email_verified_at": timezone.now(),
            "last_authenticated_at": timezone.now(),
            "status": Identity.Status.ACTIVE,
        },
    )
    return identity


def sign_in(request, identity: Identity) -> None:
    if identity.status != Identity.Status.ACTIVE:
        raise PermissionDenied("Identity unavailable")
    login(request, identity)
    request.session.cycle_key()
    request.session["auth_time"] = int(timezone.now().timestamp())


def global_sign_out(request) -> None:
    logout(request)
    request.session.flush()


class IdentityStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.status != Identity.Status.ACTIVE:
            global_sign_out(request)
            from django.http import JsonResponse

            return JsonResponse(
                {
                    "type": "about:blank",
                    "title": "Authentication required",
                    "status": 401,
                    "request_id": getattr(request, "correlation_id", "unknown"),
                },
                status=401,
                content_type="application/problem+json",
            )
        return self.get_response(request)
