from pathlib import Path

from django.conf import settings

from modules.operations.frontend import VERIFIED_REACT_ROUTES

MIGRATED_ROUTES = {
    "platform-chooser": ("public/chooser.html", "public/react_chooser.html"),
    "public-jobs-page": ("public/jobs.html", "public/react_jobs.html"),
    "public-role-page": ("candidate/application.html", "candidate/react_application.html"),
    "recruiter-search-page": ("recruiter/search.html", "recruiter/react_search.html"),
    "recruiter-results-page": ("recruiter/search.html", "recruiter/react_results.html"),
    "criteria-review-page": (
        "recruiter/criteria-review.html",
        "recruiter/react_criteria_review.html",
    ),
    "recruiter-candidate-management-page": (
        "recruiter/candidate-detail.html",
        "recruiter/react_candidate_management.html",
    ),
    "recruiter-comparison-page": (
        "recruiter/comparison.html",
        "recruiter/react_comparison.html",
    ),
    "candidate-profile-page": ("candidate/profile.html", "candidate/react_profile.html"),
    "candidate-progress-page": ("candidate/progress.html", "candidate/react_progress.html"),
    "candidate-rights-page": (
        "candidate/rights-center.html",
        "candidate/react_rights.html",
    ),
    "recruiter-organization-page": (
        "recruiter/organization.html",
        "recruiter/react_organization.html",
    ),
    "admin-jobs-page": (
        "recruiter/organization.html",
        "recruiter/react_organization.html",
    ),
    "tenant-governance-page": (
        "admin/access-review.html",
        "admin/react_governance.html",
    ),
}


def test_every_migrated_route_retains_legacy_and_reviewed_react_templates():
    assert VERIFIED_REACT_ROUTES.keys() == MIGRATED_ROUTES.keys()
    template_root = Path(settings.BASE_DIR) / "frontend" / "templates"

    for route, (legacy_template, react_template) in MIGRATED_ROUTES.items():
        registration = VERIFIED_REACT_ROUTES[route]
        assert registration == {"manifest": "react", "template": react_template}
        assert (template_root / legacy_template).is_file()
        assert (template_root / react_template).is_file()


def test_migrated_routes_remain_server_controlled_and_default_off():
    assert settings.FRONTEND_REACT_ROUTES == {}
