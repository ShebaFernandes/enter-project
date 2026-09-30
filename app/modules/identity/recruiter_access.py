from django.core.exceptions import PermissionDenied

from modules.tenancy.models import TenantMembership

PERSONAL_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"}


def validate_work_email(email: str) -> str:
    normalized = email.strip().casefold()
    if normalized.count("@") != 1 or normalized.rsplit("@", 1)[1] in PERSONAL_DOMAINS:
        raise PermissionDenied("Use a verified work identity.")
    return normalized


def require_recruiter(request) -> TenantMembership:
    membership = getattr(request, "tenant_membership", None)
    if (
        membership is None
        or membership.role
        not in {TenantMembership.Role.RECRUITER, TenantMembership.Role.HIRING_MANAGER}
        or membership.status != TenantMembership.Status.ACTIVE
    ):
        raise PermissionDenied("Recruiter workspace unavailable")
    return membership
