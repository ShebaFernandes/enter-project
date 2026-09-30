from django.urls import path

from .candidate_views import candidate_progress_page, public_application_page

urlpatterns = [
    path("roles/<uuid:opening_id>/", public_application_page, name="public-application-page"),
    path("candidate/applications/", candidate_progress_page, name="candidate-progress-page"),
]
