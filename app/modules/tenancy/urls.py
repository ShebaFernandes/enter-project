from django.urls import path

from .platform_views import TenantProvisionView
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
]
