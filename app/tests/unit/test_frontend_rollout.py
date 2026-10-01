from copy import deepcopy
from unittest.mock import patch

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, override_settings
from django.urls import resolve

from modules.operations.frontend import frontend_rollout


def page_request(query=""):
    request = RequestFactory().get(f"/candidate/profile/{query}")
    request.resolver_match = resolve("/candidate/profile/")
    return request


def test_default_and_client_flags_cannot_enable_wip():
    request = page_request("?react=true&frontend=candidate-profile-page")
    request.COOKIES["frontend"] = "react"
    assert frontend_rollout(request)["frontend_renderer"] == "legacy"
    with override_settings(FRONTEND_REACT_ROUTES={"candidate-profile-page": True}):
        assert frontend_rollout(request)["frontend_renderer"] == "legacy"


def test_verified_route_requires_explicit_boolean_flag_and_rolls_back():
    request = page_request()
    replacement = {"template": "verified.html", "script": "verified.js", "style": "verified.css"}
    with patch(
        "modules.operations.frontend.VERIFIED_REACT_ROUTES", {"candidate-profile-page": replacement}
    ):
        for flag in (False, "true", 1, None):
            with override_settings(FRONTEND_REACT_ROUTES={"candidate-profile-page": flag}):
                assert frontend_rollout(request)["frontend_renderer"] == "legacy"
        with override_settings(FRONTEND_REACT_ROUTES={"candidate-profile-page": True}):
            assert frontend_rollout(request)["frontend_renderer"] == "react"
        with override_settings(FRONTEND_REACT_ROUTES={}):
            result = frontend_rollout(request)
            assert result["frontend_renderer"] == "legacy"
            assert result["frontend_script"] == "dist/assets/app.js"
    assert request.path == "/candidate/profile/"


def test_unknown_route_fails_to_legacy():
    request = RequestFactory().get("/unknown/")
    assert frontend_rollout(request)["frontend_renderer"] == "legacy"


def test_actual_page_fallback_has_no_wip_assets_or_mounts():
    request = page_request()
    with override_settings(FRONTEND_REACT_ROUTES={"candidate-profile-page": True}):
        html = render_to_string("candidate/profile.html", request=request)
    assert 'data-frontend-renderer="legacy"' in html
    assert "data-candidate-profile" in html
    assert "data-react-candidate-profile" not in html
    assert "/wip/" not in html
    assert "/static/dist/assets/app.js" in html


def test_template_cutover_and_rollback_are_exclusive_without_route_or_data_changes():
    request = page_request()
    templates = deepcopy(settings.TEMPLATES)
    templates[0]["APP_DIRS"] = False
    options = templates[0]["OPTIONS"]
    assert isinstance(options, dict)
    options["loaders"] = [
        (
            "django.template.loaders.locmem.Loader",
            {"verified.html": "<div id='verified-root'></div>"},
        ),
        "django.template.loaders.filesystem.Loader",
    ]
    replacement = {
        "template": "verified.html",
        "script": "verified.js",
        "style": "verified.css",
    }
    with (
        override_settings(TEMPLATES=templates),
        patch(
            "modules.operations.frontend.VERIFIED_REACT_ROUTES",
            {"candidate-profile-page": replacement},
        ),
    ):
        with override_settings(FRONTEND_REACT_ROUTES={"candidate-profile-page": True}):
            html = render_to_string("candidate/profile.html", request=request)
            assert "verified-root" in html
            assert "data-candidate-profile" not in html
            assert "/static/verified.js" in html
            assert "dist/assets/app.js" not in html
        with override_settings(FRONTEND_REACT_ROUTES={"candidate-profile-page": False}):
            html = render_to_string("candidate/profile.html", request=request)
            assert "verified-root" not in html
            assert "data-candidate-profile" in html
            assert "/static/dist/assets/app.js" in html
    assert request.path == "/candidate/profile/"
