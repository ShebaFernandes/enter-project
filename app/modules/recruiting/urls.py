from django.urls import path

from .candidate_views import (
    ApplicationStatusPreviewView,
    ApplicationStatusPublishView,
    CandidateApplicationCollectionView,
    CandidateApplicationDetailView,
    CandidateApplicationWithdrawView,
    CandidateNotificationPreferencesView,
    PublicOpeningView,
)
from .opening_views import (
    OpeningCollectionView,
    OpeningDetailView,
    RecruiterEnteredCandidateCollectionView,
)

urlpatterns = [
    path("public/openings/<uuid:opening_id>", PublicOpeningView.as_view()),
    path("candidate/applications", CandidateApplicationCollectionView.as_view()),
    path(
        "candidate/applications/<uuid:application_id>",
        CandidateApplicationDetailView.as_view(),
    ),
    path(
        "candidate/applications/<uuid:application_id>/withdraw",
        CandidateApplicationWithdrawView.as_view(),
    ),
    path(
        "candidate/applications/<uuid:application_id>/notification-preferences",
        CandidateNotificationPreferencesView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/applications/<uuid:application_id>/status-preview",
        ApplicationStatusPreviewView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/applications/<uuid:application_id>/status-publish",
        ApplicationStatusPublishView.as_view(),
    ),
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
