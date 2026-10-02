from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from .context import tenant_context
from .models import EmergencyAccessRequest, TenantMembership
from .rls import tenant_transaction


def _membership(request, tenant_id, roles):
    if not request.user.is_authenticated:
        raise PermissionDenied("Governance workspace unavailable")
    token = tenant_context.set(tenant_id)
    try:
        with tenant_transaction():
            membership = TenantMembership.objects.filter(
                tenant_id=tenant_id,
                identity=request.user,
                status=TenantMembership.Status.ACTIVE,
                tenant__status="ACTIVE",
                role__in=roles,
            ).first()
    finally:
        tenant_context.reset(token)
    if membership is None:
        raise PermissionDenied("Governance workspace unavailable")
    return membership


def recruiter_organization_page(request, tenant_id):
    membership = _membership(
        request,
        tenant_id,
        [TenantMembership.Role.RECRUITER],
    )
    response = render(
        request,
        "recruiter/organization.html",
        {
            "tenant_id": tenant_id,
            "role": membership.role,
            "page_bootstrap": {
                "version": 1,
                "page": "recruiter-organization",
                "tenantId": str(tenant_id),
                "requiresSession": True,
            },
        },
    )
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response


def tenant_governance_page(request, tenant_id):
    membership = _membership(request, tenant_id, [TenantMembership.Role.TENANT_ADMIN])
    token = tenant_context.set(tenant_id)
    try:
        with tenant_transaction():
            emergency = [
                {
                    "id": str(item.id),
                    "reason_code": item.reason_code,
                    "field_scope": item.field_scope,
                    "operation_scope": item.operation_scope,
                    "object_count": len(item.object_scope.get("ids", [])),
                    "status": item.status,
                    "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                }
                for item in EmergencyAccessRequest.objects.filter(
                    tenant_id=tenant_id,
                    status=EmergencyAccessRequest.Status.ACTIVE,
                )
            ]
    finally:
        tenant_context.reset(token)
    response = render(
        request,
        "admin/access-review.html",
        {
            "tenant_id": tenant_id,
            "role": membership.role,
            "emergency_access": emergency,
            "page_bootstrap": {
                "version": 1,
                "page": "tenant-governance",
                "tenantId": str(tenant_id),
                "requiresSession": True,
                "emergencyAccess": emergency,
            },
        },
    )
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response
