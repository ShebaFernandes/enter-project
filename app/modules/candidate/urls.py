from django.urls import path

from .views import (
    CandidateProfileView,
    CandidatePublishView,
    CandidateVisibilityView,
    ResumeStateView,
    ResumeUploadView,
)

urlpatterns = [
    path("candidate/profile", CandidateProfileView.as_view()),
    path("candidate/profile/publish", CandidatePublishView.as_view()),
    path("candidate/visibility", CandidateVisibilityView.as_view()),
    path("candidate/resumes/uploads", ResumeUploadView.as_view()),
    path("candidate/resumes/<uuid:resume_id>", ResumeStateView.as_view()),
]
