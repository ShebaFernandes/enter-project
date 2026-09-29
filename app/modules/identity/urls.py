from django.urls import path

from .views import callback_view, login_start_view, session_view, sign_out_view

urlpatterns = [
    path("session", session_view),
    path("session/", session_view),
    path("session/sign-out", sign_out_view),
    path("auth/login", login_start_view),
    path("auth/callback", callback_view),
]
