from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from modules.tenancy.context import tenant_context
from modules.tenancy.models import TenantMembership
from modules.tenancy.rls import tenant_transaction


def recruiter_search_page(request, tenant_id):
    if not request.user.is_authenticated:
        raise PermissionDenied("Recruiter workspace unavailable")
    token = tenant_context.set(tenant_id)
    try:
        with tenant_transaction():
            membership = TenantMembership.objects.filter(
                tenant_id=tenant_id,
                identity=request.user,
                status=TenantMembership.Status.ACTIVE,
                role__in=[TenantMembership.Role.RECRUITER, TenantMembership.Role.HIRING_MANAGER],
            ).first()
    finally:
        tenant_context.reset(token)
    if membership is None:
        raise PermissionDenied("Recruiter workspace unavailable")
    response = render(
        request,
        "recruiter/search.html",
        {"tenant_id": membership.tenant_id, "role": membership.role},
    )
    response["Cache-Control"] = "no-store, private"
    response["Pragma"] = "no-cache"
    return response
