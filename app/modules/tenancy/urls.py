from django.urls import path

from .platform_views import TenantProvisionView
from .review_views import (
    AccessReviewCollectionView,
    AccessReviewCompleteView,
    EmergencyAccessRevokeView,
)
from .views import BusinessUnitCollectionView, BusinessUnitDetailView

urlpatterns = [
    path("platform/tenants", TenantProvisionView.as_view(), name="tenant-provision"),
    path(
        "tenants/<uuid:tenant_id>/business-units",
        BusinessUnitCollectionView.as_view(),
        name="business-unit-collection",
    ),
    path(
        "tenants/<uuid:tenant_id>/business-units/<uuid:business_unit_id>",
        BusinessUnitDetailView.as_view(),
        name="business-unit-detail",
    ),
    path(
        "tenants/<uuid:tenant_id>/access-reviews",
        AccessReviewCollectionView.as_view(),
        name="access-review-collection",
    ),
    path(
        "tenants/<uuid:tenant_id>/access-reviews/<uuid:access_review_id>/complete",
        AccessReviewCompleteView.as_view(),
        name="access-review-complete",
    ),
    path(
        "tenants/<uuid:tenant_id>/emergency-access-grants/<uuid:emergency_request_id>/revoke",
        EmergencyAccessRevokeView.as_view(),
        name="emergency-access-revoke",
    ),
]
