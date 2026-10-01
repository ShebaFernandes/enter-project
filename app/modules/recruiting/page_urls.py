from django.urls import path

from .candidate_views import candidate_progress_page, public_application_page
from .comparison_views import recruiter_comparison_page
from .views import recruiter_candidate_page

urlpatterns = [
    path("roles/<uuid:opening_id>/", public_application_page, name="public-application-page"),
    path("candidate/applications/", candidate_progress_page, name="candidate-progress-page"),
    path(
        "tenants/<uuid:tenant_id>/recruiter/comparison/",
        recruiter_comparison_page,
        name="recruiter-comparison-page",
    ),
    path(
        "tenants/<uuid:tenant_id>/recruiter/candidates/<uuid:candidate_id>/",
        recruiter_candidate_page,
        name="recruiter-candidate-page",
    ),
]
