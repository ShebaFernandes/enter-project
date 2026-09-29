from django.urls import path

from .opening_views import (
    OpeningCollectionView,
    OpeningDetailView,
    RecruiterEnteredCandidateCollectionView,
)

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
    path(
        "tenants/<uuid:tenant_id>/recruiter-entered-candidates",
        RecruiterEnteredCandidateCollectionView.as_view(),
        name="recruiter-entered-candidate-collection",
    ),
]
