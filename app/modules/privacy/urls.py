from django.urls import path

from .views import (
    RightsEscalationView,
    RightsExportDownloadView,
    RightsRequestCollectionView,
    RightsRequestDetailView,
)

urlpatterns = [
    path("candidate/rights-requests", RightsRequestCollectionView.as_view()),
    path("candidate/rights-requests/<uuid:rights_request_id>", RightsRequestDetailView.as_view()),
    path(
        "candidate/rights-requests/<uuid:rights_request_id>/download",
        RightsExportDownloadView.as_view(),
    ),
    path(
        "candidate/rights-requests/<uuid:rights_request_id>/escalations",
        RightsEscalationView.as_view(),
    ),
]
