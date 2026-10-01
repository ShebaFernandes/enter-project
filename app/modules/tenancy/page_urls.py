from django.urls import path

from .page_views import recruiter_organization_page, tenant_governance_page

urlpatterns = [
    path(
        "tenants/<uuid:tenant_id>/recruiter/organization/",
        recruiter_organization_page,
        name="recruiter-organization-page",
    ),
    path(
        "tenants/<uuid:tenant_id>/admin/governance/",
        tenant_governance_page,
        name="tenant-governance-page",
    ),
]
