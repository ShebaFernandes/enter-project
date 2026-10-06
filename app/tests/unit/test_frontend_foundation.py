import json
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import override_settings

from modules.operations.frontend import frontend_rollout
from modules.operations.frontend_assets import react_assets
from tests.unit.test_frontend_rollout import page_request


def test_manifest_assets_are_local_and_missing_build_fails_closed(tmp_path):
    assert react_assets(tmp_path) is None
    manifest = tmp_path / ".vite" / "manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "frontend/react/entry.ts": {
                    "file": "assets/app.js",
                    "isEntry": True,
                    "css": ["assets/app.css"],
                }
            }
        )
    )
    assert react_assets(tmp_path) is None
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").touch()
    (tmp_path / "assets" / "app.css").touch()
    assets = react_assets(tmp_path)
    assert assets is not None
    assert assets["script"] == "dist/react/assets/app.js"
    assert assets["style"] == "dist/react/assets/app.css"
    assert len(assets["version"]) == 16

    manifest.write_text(
        json.dumps(
            {
                "frontend/react/entry.ts": {
                    "file": "assets/app.js",
                    "isEntry": True,
                    "imports": ["_entry.js"],
                },
                "_entry.js": {
                    "file": "assets/entry.js",
                    "css": ["assets/app.css"],
                },
            }
        )
    )
    (tmp_path / "assets" / "entry.js").touch()
    imported_assets = react_assets(tmp_path)
    assert imported_assets is not None
    assert imported_assets["script"] == "dist/react/assets/app.js"
    assert imported_assets["style"] == "dist/react/assets/app.css"
    assert imported_assets["version"] != assets["version"]

    for unsafe in ("../private.js", "https://example.test/app.js", "/assets/app.js"):
        manifest.write_text(
            json.dumps(
                {
                    "frontend/react/entry.ts": {
                        "file": unsafe,
                        "isEntry": True,
                        "css": ["assets/app.css"],
                    }
                }
            )
        )
        assert react_assets(tmp_path) is None


def test_bootstrap_is_escaped_and_has_no_executable_inline_script():
    html = render_to_string(
        "react/page.html",
        {
            "page_bootstrap": {"page": "</script><script>alert(1)</script>"},
        },
    )
    assert "<script>alert(1)</script>" not in html
    assert "\\u003C/script\\u003E" in html
    assert 'type="application/json"' in html
    assert "data-page-fallback" in html
    assert 'data-page-fallback aria-label="Page recovery" tabindex="-1" hidden' in html


def test_react_assets_are_cache_versioned_in_the_page_template():
    html = render_to_string(
        "base.html",
        {
            "frontend_renderer": "react",
            "frontend_template": "react/page.html",
            "frontend_script": "dist/react/assets/app.js",
            "frontend_style": "dist/react/assets/app.css",
            "frontend_asset_version": "0123456789abcdef",
            "page_bootstrap": {"version": 1, "page": "synthetic", "requiresSession": False},
        },
    )

    assert "/static/dist/react/assets/app.js?v=0123456789abcdef" in html
    assert "/static/dist/react/assets/app.css?v=0123456789abcdef" in html


def test_missing_manifest_keeps_verified_route_on_legacy():
    registration = {"candidate-profile-page": {"manifest": "react", "template": "react/page.html"}}
    with (
        patch("modules.operations.frontend.VERIFIED_REACT_ROUTES", registration),
        patch("modules.operations.frontend.react_assets", return_value=None),
        override_settings(FRONTEND_REACT_ROUTES={"candidate-profile-page": True}),
    ):
        assert frontend_rollout(page_request())["frontend_renderer"] == "legacy"
