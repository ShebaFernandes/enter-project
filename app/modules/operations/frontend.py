"""Server-only page rollout gate. Flags remain explicitly default-off."""

from django.conf import settings
from django.http import HttpRequest

from .frontend_assets import react_assets

# Later slices register assets/template only after acceptance. WIP is excluded.
VERIFIED_REACT_ROUTES: dict[str, dict[str, str]] = {
    "platform-chooser": {"manifest": "react", "template": "public/react_chooser.html"},
    "recruiter-search-page": {"manifest": "react", "template": "recruiter/react_search.html"},
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
    approved = VERIFIED_REACT_ROUTES.get(route or "")
    if route == "recruiter-search-page" and request.GET.get("view") == "results":
        return result
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
