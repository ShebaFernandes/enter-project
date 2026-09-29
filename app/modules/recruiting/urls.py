from django.urls import path

from .opening_views import OpeningCollectionView, OpeningDetailView

urlpatterns = [
    path(
        "tenants/<uuid:tenant_id>/openings",
        OpeningCollectionView.as_view(),
        name="opening-collection",
    ),
    path(
        "tenants/<uuid:tenant_id>/openings/<uuid:opening_id>",
        OpeningDetailView.as_view(),
        name="opening-detail",
    ),
]
