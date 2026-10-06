from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import override_settings

pytestmark = pytest.mark.django_db


def test_chooser_server_gate_and_rollback_preserve_urls_and_endpoints(client):
    for flag in (False, True, False):
        with override_settings(FRONTEND_REACT_ROUTES={"platform-chooser": flag}):
            response = client.get("/?react=true")
            assert response.status_code == 200
            body = response.content.decode()
            assert f'data-frontend-renderer="{"react" if flag else "legacy"}"' in body
            assert ("data-react-page" in body) is flag
            assert ("dist/assets/app.js" in body) is not flag
            assert "/api/v1/auth/login" in body
            assert "/candidate/profile/" in body


@override_settings(LOCAL_SYNTHETIC_AUTH_ENABLED=False)
def test_recruiter_entry_is_existing_pkce_and_ignores_untrusted_return_url(client):
    response = client.get(
        "/api/v1/auth/login?next=https://untrusted.invalid/&email=private@example.test"
    )
    assert response.status_code == 302
    query = parse_qs(urlsplit(response["Location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] == [client.session["oidc_state"]]
    assert query["nonce"] == [client.session["oidc_nonce"]]
    assert "untrusted.invalid" not in response["Location"]
    assert "private@example.test" not in response["Location"]
    assert client.session["pkce_verifier"] not in response["Location"]
