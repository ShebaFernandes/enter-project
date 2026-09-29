from __future__ import annotations

import contextvars
import uuid

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse

from .models import TenantMembership

tenant_context: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar(
    "tenant_context", default=None
)


def _unavailable(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "type": "about:blank",
            "title": "Resource unavailable",
            "status": 404,
            "request_id": getattr(request, "correlation_id", "unknown"),
        },
        status=404,
        content_type="application/problem+json",
    )


def effective_role(request: HttpRequest) -> str:
    if not request.user.is_authenticated:
        raise PermissionDenied
    membership = getattr(request, "tenant_membership", None)
    if membership:
        return membership.role
    capability = (
        request.user.capabilities.filter(revoked_at__isnull=True)
        .values_list("role", flat=True)
        .first()
    )
    if capability:
        return capability
    raise PermissionDenied


class TenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        token = tenant_context.set(None)
        try:
            request.tenant_id = None
            request.tenant_membership = None
            raw = request.headers.get("X-Tenant-ID")
            if raw and request.user.is_authenticated:
                try:
                    selected = uuid.UUID(raw)
                except ValueError:
                    return _unavailable(request)
                request.tenant_id = selected
                tenant_context.set(selected)
                from .rls import tenant_transaction

                with tenant_transaction():
                    membership = TenantMembership.objects.filter(
                        tenant_id=selected,
                        identity=request.user,
                        status=TenantMembership.Status.ACTIVE,
                        tenant__status="ACTIVE",
                    ).first()
                    if membership is None:
                        return _unavailable(request)
                    request.tenant_membership = membership
                    return self.get_response(request)
            return self.get_response(request)
        finally:
            tenant_context.reset(token)
