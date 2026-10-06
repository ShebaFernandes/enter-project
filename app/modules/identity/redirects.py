from django.utils.http import url_has_allowed_host_and_scheme


def safe_candidate_return_to(request) -> str:
    value = str(request.query_params.get("return_to", "")).strip()
    if not value.startswith(("/roles/", "/candidate/", "/jobs/")):
        return ""
    if value.startswith("//") or not url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return ""
    return value
