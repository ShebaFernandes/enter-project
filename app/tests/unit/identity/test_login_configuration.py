from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from django.test import RequestFactory, override_settings

from modules.identity.services import start_login
from modules.identity.views import login_start_view


def test_oauth_login_uses_hosted_domain(settings):
    env = replace(settings.ENV, cognito_domain="https://signin.example.com")
    with override_settings(ENV=env):
        parsed = urlparse(start_login().authorization_url)
    assert parsed.netloc == "signin.example.com"
    assert parsed.path == "/oauth2/authorize"


def test_local_login_uses_synthetic_bootstrap(settings):
    request = RequestFactory().get("/api/v1/auth/login")
    request.session = {}
    with (
        override_settings(
            ENV=replace(settings.ENV, app_env="local"), LOCAL_SYNTHETIC_AUTH_ENABLED=True
        ),
        patch(
            "modules.identity.local_auth.issue_local_recruiter_bootstrap",
            return_value=SimpleNamespace(token="test-token"),  # noqa: S106
        ),
    ):
        response = login_start_view(request)
    assert response.url == "/api/v1/__local__/synthetic-recruiter-session?token=test-token"
    assert response["Cache-Control"] == "no-store, private"


def test_production_never_uses_synthetic_login(settings):
    request = RequestFactory().get("/api/v1/auth/login")
    request.session = {}
    env = replace(settings.ENV, app_env="production", cognito_domain="https://signin.example.com")
    with (
        override_settings(ENV=env, LOCAL_SYNTHETIC_AUTH_ENABLED=True),
        patch("modules.identity.local_auth.issue_local_recruiter_bootstrap") as issue,
    ):
        response = login_start_view(request)
    issue.assert_not_called()
    assert response.url.startswith("https://signin.example.com/oauth2/authorize?")
    assert request.session["pkce_verifier"]
