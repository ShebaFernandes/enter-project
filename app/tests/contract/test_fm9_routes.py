import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_candidate_profile_flag_is_independent_default_off_and_reversible(
    client, profile_factory, settings
):
    candidate_profile = profile_factory()
    client.force_login(candidate_profile.identity)
    path = "/candidate/profile/"

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-candidate-profile" in client.get(path).content

    settings.FRONTEND_REACT_ROUTES = {"candidate-profile-page": True}
    response = client.get(path)
    assert response.status_code == 200
    assert b'data-frontend-renderer="react"' in response.content
    assert b'"page": "candidate-profile"' in response.content
    assert b"data-candidate-profile" not in response.content
    assert "no-store" in response["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-candidate-profile" in client.get(path).content
