from __future__ import annotations

import hashlib
import time

from django.core.cache import cache
from django.http import JsonResponse

from .policy import LIMITS, active_override, escalation_delay, tightened

PATH_ACTIONS = {
    "/auth/login": "sign-in",
    "/otp": "otp",
    "/resume": "upload",
    "/applications": "application",
    "/searches": "search",
    "/exports": "export",
}


def signal_token(request) -> str:
    identity = (
        str(request.user.pk) if getattr(request.user, "is_authenticated", False) else "anonymous"
    )
    network = request.META.get("REMOTE_ADDR", "unknown")
    return hashlib.sha256(f"{identity}|{network}".encode()).hexdigest()


def action_for_path(path: str) -> str | None:
    return next((action for fragment, action in PATH_ACTIONS.items() if fragment in path), None)


def check(request, action: str, anomaly_score: int = 0) -> tuple[bool, int, int]:
    limit = tightened(LIMITS[action], anomaly_score)
    subject_token = signal_token(request)
    if active_override(subject_token=subject_token, action=action):
        return True, limit.attempts, 0
    bucket = int(time.time()) // limit.window_seconds
    key = f"rate:{action}:{subject_token}:{bucket}"
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=limit.window_seconds)
        count = 1
    remaining = max(0, limit.attempts - count)
    if count <= limit.attempts:
        return True, remaining, 0
    return False, 0, escalation_delay(count - limit.attempts)


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        action = action_for_path(request.path)
        if action:
            allowed, remaining, retry_after = check(request, action)
            if not allowed:
                response = JsonResponse(
                    {
                        "type": "about:blank",
                        "title": "Temporarily rate limited",
                        "status": 429,
                        "request_id": getattr(request, "correlation_id", "unknown"),
                    },
                    status=429,
                    content_type="application/problem+json",
                )
                response["Retry-After"] = str(retry_after)
                response["X-RateLimit-Remaining"] = "0"
                return response
            request.rate_limit_remaining = remaining
        response = self.get_response(request)
        if action:
            response.setdefault(
                "X-RateLimit-Remaining", str(getattr(request, "rate_limit_remaining", 0))
            )
        return response
