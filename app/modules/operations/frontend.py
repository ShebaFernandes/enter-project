"""Server-only page rollout gate. Flags remain explicitly default-off."""

from django.conf import settings
from django.http import HttpRequest

from .frontend_assets import react_assets

# Later slices register assets/template only after acceptance. WIP is excluded.
VERIFIED_REACT_ROUTES: dict[str, dict[str, str]] = {
    "recruiter-comparison-page": {
        "manifest": "react",
        "template": "recruiter/react_comparison.html",
    },
    "recruiter-candidate-management-page": {
        "manifest": "react",
        "template": "recruiter/react_candidate_management.html",
    },
    "platform-chooser": {"manifest": "react", "template": "public/react_chooser.html"},
    "recruiter-search-page": {"manifest": "react", "template": "recruiter/react_search.html"},
    "recruiter-results-page": {"manifest": "react", "template": "recruiter/react_results.html"},
    "criteria-review-page": {
        "manifest": "react",
        "template": "recruiter/react_criteria_review.html",
    },
}


def frontend_rollout(request: HttpRequest) -> dict[str, str]:
    result = {
        "frontend_renderer": "legacy",
        "frontend_template": "",
        "frontend_script": "dist/assets/app.js",
        "frontend_style": "dist/assets/app.css",
    }
    match = request.resolver_match
    route = match.url_name if match else None
    flags = getattr(settings, "FRONTEND_REACT_ROUTES", {})
    if route == "recruiter-search-page" and request.GET.get("view") == "results":
        route = "recruiter-results-page"
    if route == "recruiter-candidate-page":
        route = "recruiter-candidate-management-page"
    approved = VERIFIED_REACT_ROUTES.get(route or "")
    if approved and isinstance(flags, dict) and flags.get(route) is True:
        if approved.get("manifest") == "react":
            assets = react_assets(settings.BASE_DIR / "static" / "dist" / "react")
            if assets is None:
                return result
            approved = {**approved, **assets}
        result.update(
            frontend_renderer="react",
            frontend_template=approved["template"],
            frontend_script=approved["script"],
            frontend_style=approved["style"],
        )
    return result
