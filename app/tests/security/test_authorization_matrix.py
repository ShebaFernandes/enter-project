import uuid

import pytest
from django.core.exceptions import PermissionDenied

from modules.tenancy.models import TenantMembership
from modules.tenancy.policy import ROLE_ACTIONS, AuthorizationRequest, authorize


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("CANDIDATE", {"own.read", "own.write"}),
        (
            TenantMembership.Role.RECRUITER,
            {"business_unit.read", "business_unit.write", "opening.read", "opening.write"},
        ),
        (TenantMembership.Role.HIRING_MANAGER, {"opening.read"}),
        (
            TenantMembership.Role.TENANT_ADMIN,
            {
                "business_unit.read",
                "business_unit.write",
                "opening.read",
                "opening.write",
                "tenant.admin",
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
