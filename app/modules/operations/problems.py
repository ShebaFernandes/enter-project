from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .concurrency import StaleWrite
from .idempotency import IdempotencyConflict


def problem(
    *,
    title: str,
    status_code: int,
    request_id: str,
    detail: str = "",
    errors: dict[str, list[str]] | None = None,
) -> Response:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "request_id": request_id,
    }
    if detail:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    return Response(body, status=status_code, content_type="application/problem+json")


def problem_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    request = context.get("request")
    request_id = getattr(request, "correlation_id", "unknown")
    if isinstance(exc, (PermissionDenied, Http404)):
        return problem(
            title="Resource unavailable",
            status_code=status.HTTP_404_NOT_FOUND,
            request_id=request_id,
        )
    if isinstance(exc, (ValidationError, DRFValidationError)):
        response = problem(
            title="Validation failed",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            request_id=request_id,
        )
        response.data["errors"] = getattr(exc, "detail", getattr(exc, "message_dict", {}))
        return response
    if isinstance(exc, IdempotencyConflict):
        return problem(
            title="Idempotency conflict",
            status_code=status.HTTP_409_CONFLICT,
            request_id=request_id,
        )
    if isinstance(exc, StaleWrite):
        details = exc.reconciliation
        body = {
            "type": "about:blank",
            "title": "Stale write rejected",
            "status": 409,
            "request_id": request_id,
            **details,
        }
        return Response(body, status=409, content_type="application/problem+json")
    default_response = exception_handler(exc, context)
    if default_response is not None:
        default_response.data = {
            "type": "about:blank",
            "title": "Request failed",
            "status": default_response.status_code,
            "request_id": request_id,
        }
        default_response.content_type = "application/problem+json"
    return default_response
