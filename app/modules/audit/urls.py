from django.urls import path

from .views import TenantAuditEventView

urlpatterns = [
    path(
        "tenants/<uuid:tenant_id>/audit-events",
        TenantAuditEventView.as_view(),
        name="tenant-audit-events",
    )
]
