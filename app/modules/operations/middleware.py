from __future__ import annotations

import contextvars
import logging
import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")
_SENSITIVE = re.compile(
    r"(?i)(authorization|cookie|token|password|secret|email|phone|resume)([=:]\s*)([^\s,;]+)"
)


class CorrelationIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = correlation_id.set(request_id)
        request.correlation_id = request_id
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            correlation_id.reset(token)


class SecurityHeadersMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
        response.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=()")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _SENSITIVE.sub(r"\1\2[REDACTED]", str(record.msg))
        record.args = ()
        return True


class ProgressEvent:
    def __init__(self, state: str, message: str, percent: int | None = None) -> None:
        self.state = state
        self.message = message
        self.percent = percent

    def as_dict(self) -> dict[str, str | int | None]:
        return {"state": self.state, "message": self.message, "percent": self.percent}
