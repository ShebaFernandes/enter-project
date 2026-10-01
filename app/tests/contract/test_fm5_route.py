import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.postgres]


def test_review_flag_bootstrap_exclusive_ownership_and_rollback(client, recruiter, settings):
    route = f"/tenants/{recruiter.tenant_id}/recruiter/search/criteria-review/"
    client.force_login(recruiter.identity)
    settings.FRONTEND_REACT_ROUTES = {}
    assert 'data-frontend-renderer="legacy"' in client.get(route).content.decode()
    settings.FRONTEND_REACT_ROUTES = {"criteria-review-page": True}
    response = client.get(route)
    html = response.content.decode()
    assert 'data-frontend-renderer="react"' in html
    assert '"page": "criteria-review"' in html
    assert "data-criteria-review" not in html
    assert "dist/assets/app.js" not in html
    assert "no-store" in response["Cache-Control"]
    settings.FRONTEND_REACT_ROUTES = {}
    assert 'data-frontend-renderer="legacy"' in client.get(route).content.decode()
    recruiter.role = "TENANT_ADMIN"
    recruiter.save()
    settings.FRONTEND_REACT_ROUTES = {"criteria-review-page": True}
    assert client.get(route).status_code == 403


def test_review_flag_does_not_enable_results(client, recruiter, settings):
    client.force_login(recruiter.identity)
    settings.FRONTEND_REACT_ROUTES = {"criteria-review-page": True}
    response = client.get(f"/tenants/{recruiter.tenant_id}/recruiter/search/?view=results")
    assert 'data-frontend-renderer="legacy"' in response.content.decode()
