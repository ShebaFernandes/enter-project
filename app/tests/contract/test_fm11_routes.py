import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_candidate_progress_flag_is_default_off_independent_and_reversible(
    client, profile_factory, settings
):
    profile = profile_factory()
    client.force_login(profile.identity)
    path = "/candidate/applications/"

    settings.FRONTEND_REACT_ROUTES = {}
    legacy = client.get(path)
    assert legacy.status_code == 200
    assert b"data-progress-page" in legacy.content
    assert b"data-react-page" not in legacy.content

    settings.FRONTEND_REACT_ROUTES = {"candidate-progress-page": True}
    react = client.get(path)
    assert react.status_code == 200
    assert b'data-frontend-renderer="react"' in react.content
    assert b'"page": "candidate-progress"' in react.content
    assert b'"requiresSession": true' in react.content
    assert str(profile.id).encode() not in react.content
    assert b"data-progress-page" not in react.content
    assert "no-store" in react["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {}
    assert b"data-progress-page" in client.get(path).content


def test_candidate_rights_flag_is_default_off_independent_and_reversible(
    client, profile_factory, settings
):
    profile = profile_factory()
    client.force_login(profile.identity)
    path = "/candidate/rights/"

    settings.FRONTEND_REACT_ROUTES = {}
    legacy = client.get(path)
    assert legacy.status_code == 200
    assert b"data-rights-center" in legacy.content
    assert b"data-react-page" not in legacy.content

    settings.FRONTEND_REACT_ROUTES = {"candidate-rights-page": True}
    react = client.get(path)
    assert react.status_code == 200
    assert b'data-frontend-renderer="react"' in react.content
    assert b'"page": "candidate-rights"' in react.content
    assert b'"requiresSession": true' in react.content
    assert str(profile.id).encode() not in react.content
    assert b"data-rights-center" not in react.content
    assert "no-store" in react["Cache-Control"]

    settings.FRONTEND_REACT_ROUTES = {"candidate-progress-page": True}
    assert b"data-rights-center" in client.get(path).content
