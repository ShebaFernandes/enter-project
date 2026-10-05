from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from django.conf import settings
from django.contrib.auth import login, logout
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from modules.operations.crypto import blind_index, decrypt, encrypt

from .models import Identity, IdentityCapability, SessionCredential, StepUpEvidence


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
        f"{settings.ENV.cognito_domain.rstrip('/')}/oauth2/authorize?{urlencode(params)}",
        state,
        nonce,
        verifier,
    )


def exchange_code(code: str, verifier: str) -> dict[str, object]:
    if settings.ENV.app_env in {"local", "test"}:
        raise PermissionDenied("External identity exchange is unavailable in local/test mode")
    response = httpx.post(
        f"{settings.ENV.cognito_domain.rstrip('/')}/oauth2/token",
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
    email_key = blind_index(email, purpose="verified-email")
    identity = Identity.objects.filter(email_lookup_hmac=email_key).first()
    if identity is not None and identity.cognito_subject != subject:
        raise PermissionDenied("Verified identity unavailable")
    identity, _ = Identity.objects.update_or_create(
        cognito_subject=subject,
        defaults={
            "email_lookup_hmac": email_key,
            "email_ciphertext": encrypt(email),
            "email_verified_at": timezone.now(),
            "last_authenticated_at": timezone.now(),
            "status": Identity.Status.ACTIVE,
        },
    )
    return identity


def _claim_values(claims: dict[str, object], name: str) -> set[str]:
    raw = claims.get(name, ())
    if isinstance(raw, str):
        return {raw.casefold()}
    if isinstance(raw, (list, tuple)):
        return {str(value).casefold() for value in raw}
    return set()


def assurance_from_claims(claims: dict[str, object], *, workforce: bool) -> str:
    methods = _claim_values(claims, "amr") | _claim_values(claims, "cognito:amr")
    if workforce:
        if not ({"mfa", "otp", "totp", "webauthn"} & methods):
            raise PermissionDenied("Multi-factor assurance required")
        return SessionCredential.Assurance.WORKFORCE_MFA
    if claims.get("email_verified") is not True:
        raise PermissionDenied("Verified identity required")
    if methods and not ({"otp", "email", "magic_link", "mfa"} & methods):
        raise PermissionDenied("Verified email assurance required")
    return SessionCredential.Assurance.VERIFIED_EMAIL_OTP


def link_identity_with_role(claims: dict[str, object], *, workforce: bool) -> Identity:
    assurance_from_claims(claims, workforce=workforce)
    if workforce:
        # Workforce entry is deliberately narrower than candidate identity linking:
        # verified personal-mail identities cannot enter a recruiter workspace.
        from .recruiter_access import validate_work_email

        validate_work_email(str(claims.get("email", "")))
    identity = link_verified_identity(claims)
    if not workforce:
        IdentityCapability.objects.get_or_create(
            identity=identity,
            role=IdentityCapability.Role.CANDIDATE,
            revoked_at__isnull=True,
            defaults={"assigned_by": identity},
        )
    return identity


def sign_in(
    request,
    identity: Identity,
    *,
    claims: dict[str, object] | None = None,
    refresh_token: str | None = None,
    workforce: bool = False,
) -> SessionCredential:
    if identity.status != Identity.Status.ACTIVE:
        raise PermissionDenied("Identity unavailable")
    assurance = assurance_from_claims(claims or {"email_verified": True}, workforce=workforce)
    login(request, identity)
    request.session.cycle_key()
    if request.session.session_key is None:
        request.session.save()
    authenticated_at = timezone.now()
    session_key = str(request.session.session_key)
    credential = SessionCredential.objects.create(
        identity=identity,
        session_key_hash=hashlib.sha256(session_key.encode()).digest(),
        provider_session_id=str((claims or {}).get("origin_jti", "")),
        provider=str((claims or {}).get("identities", "COGNITO"))[:80],
        assurance=assurance,
        refresh_token_ciphertext=encrypt(refresh_token) if refresh_token else None,
        authenticated_at=authenticated_at,
        expires_at=authenticated_at + timedelta(seconds=request.session.get_expiry_age()),
    )
    request.session["auth_time"] = int(authenticated_at.timestamp())
    request.session["session_credential_id"] = str(credential.id)
    request.session["session_assurance"] = assurance
    return credential


def revoke_session(credential: SessionCredential, *, reason: str) -> None:
    if credential.revoked_at is None:
        credential.revoked_at = timezone.now()
        credential.revocation_reason = reason
        credential.save(update_fields=("revoked_at", "revocation_reason"))


def _revoke_provider_token(credential: SessionCredential) -> None:
    if not credential.refresh_token_ciphertext or settings.ENV.app_env in {"local", "test"}:
        return
    response = httpx.post(
        f"{settings.ENV.cognito_domain.rstrip('/')}/oauth2/revoke",
        data={
            "token": decrypt(bytes(credential.refresh_token_ciphertext)),
            "client_id": settings.ENV.cognito_client_id,
            "client_secret": settings.ENV.cognito_client_secret,
        },
        timeout=10,
    )
    response.raise_for_status()


def global_sign_out(request) -> None:
    credential_id = request.session.get("session_credential_id")
    if credential_id:
        credential = SessionCredential.objects.filter(pk=credential_id).first()
        if credential is not None:
            _revoke_provider_token(credential)
            revoke_session(credential, reason="USER_SIGN_OUT")
    logout(request)
    request.session.flush()


def begin_step_up(request, *, purpose: str) -> tuple[str, str]:
    current_session_credential(request)
    nonce = secrets.token_urlsafe(32)
    request.session["step_up_nonce_hash"] = hashlib.sha256(nonce.encode()).hexdigest()
    request.session["step_up_purpose"] = purpose
    request.session["step_up_started_at"] = int(timezone.now().timestamp())
    return nonce, purpose


def complete_step_up(
    request, *, claims: dict[str, object], expected_nonce: str, purpose: str
) -> StepUpEvidence:
    credential = current_session_credential(request)
    if str(claims.get("sub", "")) != request.user.cognito_subject:
        raise PermissionDenied("Step-up identity mismatch")
    if str(claims.get("nonce", "")) != expected_nonce:
        raise PermissionDenied("Step-up challenge mismatch")
    if (
        request.session.pop("step_up_nonce_hash", "")
        != hashlib.sha256(expected_nonce.encode()).hexdigest()
    ):
        raise PermissionDenied("Step-up challenge unavailable")
    if request.session.pop("step_up_purpose", "") != purpose:
        raise PermissionDenied("Step-up purpose mismatch")
    auth_time = claims.get("auth_time", 0)
    if not isinstance(auth_time, (int, float, str)):
        raise PermissionDenied("Step-up authentication time is invalid")
    issued_at = datetime.fromtimestamp(int(auth_time), tz=UTC)
    if timezone.now() - issued_at > timedelta(minutes=5):
        raise PermissionDenied("Step-up authentication is stale")
    method = assurance_from_claims(claims, workforce=False)
    now = timezone.now()
    evidence = StepUpEvidence.objects.create(
        identity=request.user,
        session_credential=credential,
        purpose=purpose,
        method=method,
        nonce_hash=hashlib.sha256(expected_nonce.encode()).digest(),
        verified_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    request.session["step_up_evidence_id"] = str(evidence.id)
    return evidence


def current_session_credential(request) -> SessionCredential:
    credential_id = request.session.get("session_credential_id")
    if not credential_id:
        raise PermissionDenied("Assured session required")
    credential = SessionCredential.objects.filter(
        pk=credential_id,
        identity=request.user,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if credential is None:
        raise PermissionDenied("Assured session unavailable")
    return credential


def require_recent_step_up(request, *, purpose: str) -> StepUpEvidence:
    credential = current_session_credential(request)
    evidence_id = request.session.get("step_up_evidence_id")
    evidence = StepUpEvidence.objects.filter(
        pk=evidence_id,
        identity=request.user,
        session_credential=credential,
        purpose=purpose,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()
    if evidence is None:
        raise PermissionDenied("Recent step-up authentication required")
    return evidence


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
        credential_id = request.session.get("session_credential_id")
        if request.user.is_authenticated and credential_id:
            valid = SessionCredential.objects.filter(
                pk=credential_id,
                identity=request.user,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).exists()
            if not valid:
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
