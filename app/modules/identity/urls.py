from django.conf import settings
from django.urls import path

from .views import callback_view, login_start_view, session_view, sign_out_view

urlpatterns = [
    path("session", session_view),
    path("session/", session_view),
    path("session/sign-out", sign_out_view),
    path("auth/login", login_start_view),
    path("auth/callback", callback_view),
]

if settings.LOCAL_SYNTHETIC_AUTH_ENABLED:
    from .local_views import local_candidate_session_view, local_recruiter_session_view

    urlpatterns.append(
        path(
            "__local__/synthetic-recruiter-session",
            local_recruiter_session_view,
            name="local-synthetic-recruiter-session",
        )
    )
    urlpatterns.append(
        path(
            "__local__/synthetic-candidate-session",
            local_candidate_session_view,
            name="local-synthetic-candidate-session",
        )
    )
