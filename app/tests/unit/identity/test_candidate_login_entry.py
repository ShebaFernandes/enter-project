from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.test import RequestFactory, override_settings

from modules.identity.views import login_start_view


def test_local_candidate_login_selects_candidate_bootstrap(settings):
    request = RequestFactory().get("/api/v1/auth/login?platform=candidate")
    request.session = SessionStore()
    with (
        override_settings(
            ENV=replace(settings.ENV, app_env="local"), LOCAL_SYNTHETIC_AUTH_ENABLED=True
        ),
        patch(
            "modules.identity.local_auth.issue_local_candidate_bootstrap",
            return_value=SimpleNamespace(token="test-token"),  # noqa: S106 -- synthetic fixture
        ),
        patch("modules.identity.local_auth.issue_local_recruiter_bootstrap") as recruiter,
    ):
        response = login_start_view(request)
    recruiter.assert_not_called()
    assert (
        response.url == "/api/v1/__local__/synthetic-candidate-session?token=test-token&profile=1"
    )
    assert response["Cache-Control"] == "no-store, private"


def test_candidate_parameter_cannot_enable_synthetic_login_in_production(settings):
    request = RequestFactory().get("/api/v1/auth/login?platform=candidate")
    request.session = SessionStore()
    with (
        override_settings(
            ENV=replace(
                settings.ENV, app_env="production", cognito_domain="https://signin.example.com"
            ),
            LOCAL_SYNTHETIC_AUTH_ENABLED=True,
        ),
        patch("modules.identity.local_auth.issue_local_candidate_bootstrap") as candidate,
    ):
        response = login_start_view(request)
    candidate.assert_not_called()
    assert response.url.startswith("https://signin.example.com/oauth2/authorize?")


def test_local_results_navigation_preserves_destination(settings):
    request = RequestFactory().get("/api/v1/auth/login?view=results")
    request.session = SessionStore()
    with (
        override_settings(
            ENV=replace(settings.ENV, app_env="local"), LOCAL_SYNTHETIC_AUTH_ENABLED=True
        ),
        patch(
            "modules.identity.local_auth.issue_local_recruiter_bootstrap",
            return_value=SimpleNamespace(token="test-token"),  # noqa: S106 -- synthetic fixture
        ),
    ):
        response = login_start_view(request)
    assert response.url.endswith("?token=test-token&view=results")


def test_legacy_results_link_opens_results_entry():
    from modules.recruiting.public_views import platform_chooser

    response = platform_chooser(RequestFactory().get("/?view=results"))
    assert response.url == "/api/v1/auth/login?view=results"
