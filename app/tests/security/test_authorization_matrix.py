import hashlib
import uuid
from datetime import timedelta
from typing import cast

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework.test import APIClient

from modules.audit.models import AuditEvent
from modules.identity.models import SessionCredential
from modules.tenancy.models import AccessGrant, TenantMembership
from modules.tenancy.policy import ROLE_ACTIONS, AuthorizationRequest, authorize
from tests.factories import AccessGrantFactory


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        (
            "CANDIDATE",
            {"own.read", "own.write", "rights.use", "resume.own.read", "application.own"},
        ),
        (
            TenantMembership.Role.RECRUITER,
            {
                "business_unit.read",
                "business_unit.write",
                "opening.read",
                "opening.write",
                "candidate.search",
                "candidate.read",
                "candidate.field.read",
                "candidate.compare",
                "recruiter_candidate.create",
                "recruiter_candidate.read",
                "application.read",
                "application.status.write",
                "application.status.publish",
                "candidate_work.read",
                "candidate_work.write",
                "recruiter_note.read",
                "recruiter_note.write",
                "shortlist.write",
                "candidate.disclosure.preview",
                "candidate.disclosure.confirm",
                "audit.read",
                "saved_search.manage",
            },
        ),
        (
            TenantMembership.Role.HIRING_MANAGER,
            {
                "opening.read",
                "candidate.search",
                "candidate.read",
                "candidate.field.read",
                "candidate.compare",
                "recruiter_candidate.read",
                "application.read",
                "application.status.write",
                "application.status.publish",
                "candidate_work.read",
                "candidate_work.write",
                "recruiter_note.read",
                "recruiter_note.write",
                "shortlist.write",
                "candidate.disclosure.preview",
                "candidate.disclosure.confirm",
                "audit.read",
                "saved_search.manage",
            },
        ),
        (
            TenantMembership.Role.TENANT_ADMIN,
            {
                "business_unit.read",
                "business_unit.write",
                "opening.read",
                "opening.write",
                "tenant.admin",
                "audit.read",
                "access_review.manage",
                "membership.admin",
            },
        ),
        ("PLATFORM_SECURITY_ADMIN", {"platform.tenant.provision", "security.admin"}),
    ],
)
def test_five_fixed_roles_have_exact_launch_actions(role, allowed):
    assert ROLE_ACTIONS[role] == frozenset(allowed)


def test_unknown_action_is_denied():
    with pytest.raises(PermissionDenied):
        authorize(
            AuthorizationRequest(
                action="candidate.content.read",
                role=TenantMembership.Role.TENANT_ADMIN,
                tenant_id=uuid.uuid4(),
            )
        )


def test_cross_tenant_guessed_identifier_is_denied():
    with pytest.raises(PermissionDenied):
        authorize(
            AuthorizationRequest(
                action="opening.read",
                role=TenantMembership.Role.RECRUITER,
                tenant_id=uuid.uuid4(),
                object_tenant_id=uuid.uuid4(),
            )
        )


@pytest.mark.django_db
def test_sensitive_candidate_access_requires_exact_purpose_fields_object_and_grant(
    identity, recruiter, tenant
):
    candidate_id = str(uuid.uuid4())
    grant = cast(
        AccessGrant,
        AccessGrantFactory(
            tenant=tenant,
            grantee=identity,
            purpose_code="RECRUITING_REVIEW",
            field_scope=["profile_state", "skills"],
            object_scope={"ids": [candidate_id]},
        ),
    )
    request = AuthorizationRequest(
        action="candidate.field.read",
        role=recruiter.role,
        tenant_id=tenant.id,
        object_tenant_id=tenant.id,
        object_id=candidate_id,
        purpose="RECRUITING_REVIEW",
        fields=frozenset({"skills"}),
        consent_purposes=frozenset({"RECRUITING_REVIEW"}),
        consent_fields=frozenset({"profile_state", "skills"}),
        grant=grant,
        actor=identity,
        sensitive=True,
    )
    authorize(request)
    for altered in (
        {"purpose": "CONTACT"},
        {"fields": frozenset({"email"})},
        {"object_id": str(uuid.uuid4())},
        {"tenant_id": uuid.uuid4()},
    ):
        with pytest.raises(PermissionDenied):
            authorize(AuthorizationRequest(**{**request.__dict__, **altered}))
    assert AuditEvent.objects.filter(outcome="DENIED").count() == 4


@pytest.mark.django_db
def test_expired_or_revoked_grants_are_denied(identity, recruiter, tenant):
    candidate_id = str(uuid.uuid4())
    grant = cast(
        AccessGrant,
        AccessGrantFactory(
            tenant=tenant,
            grantee=identity,
            object_scope={"ids": [candidate_id]},
            valid_from=timezone.now() - timedelta(hours=2),
            expires_at=timezone.now() - timedelta(hours=1),
        ),
    )
    with pytest.raises(PermissionDenied):
        authorize(
            AuthorizationRequest(
                action="candidate.field.read",
                role=recruiter.role,
                tenant_id=tenant.id,
                object_tenant_id=tenant.id,
                object_id=candidate_id,
                purpose=grant.purpose_code,
                fields=frozenset(grant.field_scope),
                consent_purposes=frozenset({grant.purpose_code}),
                consent_fields=frozenset(grant.field_scope),
                grant=grant,
                actor=identity,
                sensitive=True,
            )
        )


def test_every_role_denies_every_unlisted_operation():
    all_actions = set().union(*ROLE_ACTIONS.values()) | {"unknown.operation"}
    for role, allowed in ROLE_ACTIONS.items():
        for action in all_actions - set(allowed):
            with pytest.raises(PermissionDenied):
                authorize(AuthorizationRequest(action=action, role=role, tenant_id=None))


@pytest.mark.django_db
def test_revoked_session_is_denied_server_side(identity):
    client = APIClient()
    client.force_login(identity)
    session = client.session
    assert session.session_key is not None
    credential = SessionCredential.objects.create(
        identity=identity,
        session_key_hash=hashlib.sha256(session.session_key.encode()).digest(),
        provider="COGNITO",
        assurance=SessionCredential.Assurance.VERIFIED_EMAIL_OTP,
        authenticated_at=timezone.now(),
        expires_at=timezone.now() + timedelta(minutes=30),
        revoked_at=timezone.now(),
        revocation_reason="SECURITY_REVOKED",
    )
    session["session_credential_id"] = str(credential.id)
    session.save()
    assert client.get("/api/v1/session").status_code == 401


@pytest.mark.django_db
def test_stale_link_and_tenant_switch_require_current_membership(identity, tenant):
    client = APIClient()
    client.force_login(identity)
    stale_link = client.get(
        f"/api/v1/tenants/{tenant.id}/business-units",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    tenant_switch = client.get("/api/v1/session", HTTP_X_TENANT_ID=str(tenant.id))
    assert stale_link.status_code == 404
    assert tenant_switch.status_code == 404
