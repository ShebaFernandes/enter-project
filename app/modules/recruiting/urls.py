from django.urls import path

from .candidate_views import (
    ApplicationStatusPreviewView,
    ApplicationStatusPublishView,
    CandidateApplicationCollectionView,
    CandidateApplicationDetailView,
    CandidateApplicationPreparationView,
    CandidateApplicationReadinessView,
    CandidateApplicationWithdrawView,
    CandidateNotificationPreferencesView,
)
from .comparison_views import ComparisonView
from .opening_views import (
    OpeningApplicationCollectionView,
    OpeningCollectionView,
    OpeningDetailView,
    OpeningPublicationView,
    RecruiterEnteredCandidateCollectionView,
)
from .public_views import PublicOpeningCollectionView
from .views import (
    ApplicationInternalStatusView,
    ApplicationNoteCollectionView,
    ApplicationResumeView,
    CandidateWorkCollectionView,
    CandidateWorkDetailView,
    CandidateWorkNoteCollectionView,
    DisclosureConfirmView,
    DisclosurePreviewView,
)

urlpatterns = [
    path(
        "tenants/<uuid:tenant_id>/openings/<uuid:opening_id>/publication",
        OpeningPublicationView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/openings/<uuid:opening_id>/publication/publish",
        OpeningPublicationView.as_view(),
        {"action": "publish"},
    ),
    path(
        "tenants/<uuid:tenant_id>/openings/<uuid:opening_id>/publication/withdraw",
        OpeningPublicationView.as_view(),
        {"action": "withdraw"},
    ),
    path("public/openings", PublicOpeningCollectionView.as_view()),
    path("public/openings/<uuid:opening_id>", PublicOpeningCollectionView.as_view()),
    path(
        "candidate/applications/readiness",
        CandidateApplicationReadinessView.as_view(),
    ),
    path(
        "candidate/applications/prepare",
        CandidateApplicationPreparationView.as_view(),
    ),
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
        "tenants/<uuid:tenant_id>/applications/<uuid:context_id>/notes",
        ApplicationNoteCollectionView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/applications/<uuid:application_id>/internal-status",
        ApplicationInternalStatusView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/applications/<uuid:application_id>/resume",
        ApplicationResumeView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/candidate-work",
        CandidateWorkCollectionView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/candidate-work/<uuid:candidate_work_id>",
        CandidateWorkDetailView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/candidate-work/<uuid:context_id>/notes",
        CandidateWorkNoteCollectionView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/comparisons",
        ComparisonView.as_view(),
        name="candidate-comparison",
    ),
    path(
        "tenants/<uuid:tenant_id>/candidates/<uuid:candidate_id>/disclosures/preview",
        DisclosurePreviewView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/candidates/<uuid:candidate_id>/disclosures",
        DisclosureConfirmView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/openings",
        OpeningCollectionView.as_view(),
        name="opening-collection",
    ),
    path(
        "tenants/<uuid:tenant_id>/openings/<uuid:opening_id>/applications",
        OpeningApplicationCollectionView.as_view(),
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
