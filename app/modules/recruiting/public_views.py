import uuid

from django.db import DatabaseError
from django.shortcuts import redirect, render
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .public_openings import available_publications, public_data, public_reader


class PublicOpeningThrottle(SimpleRateThrottle):
    scope = "public-openings"
    rate = "60/min"

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as exc:
            error = APIException("Public roles are temporarily unavailable.")
            error.status_code = 503
            raise error from exc

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class PublicOpeningCollectionView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicOpeningThrottle]
    http_method_names = ["get", "head", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def get(self, request, opening_id=None):
        try:
            limit = int(request.query_params.get("limit", "25"))
            if not 1 <= limit <= 100:
                raise ValueError
            raw_cursor = request.query_params.get("cursor")
            cursor = uuid.UUID(raw_cursor) if raw_cursor else None
        except (ValueError, TypeError) as exc:
            raise serializers.ValidationError("Invalid pagination.") from exc
        try:
            with public_reader():
                rows = available_publications()
                if opening_id is not None:
                    item = rows.filter(pk=opening_id).first()
                    return Response(public_data(item)) if item else Response(status=404)
                if cursor:
                    rows = rows.filter(id__gt=cursor)
                items = list(rows.order_by("id")[: limit + 1])
                return Response(
                    {
                        "items": [public_data(item) for item in items[:limit]],
                        "next_cursor": str(items[limit - 1].id) if len(items) > limit else None,
                    }
                )
        except DatabaseError:
            return Response({"title": "Public roles are temporarily unavailable."}, status=503)


def platform_chooser(request):
    if request.GET.get("view") == "results":
        return redirect("/api/v1/auth/login?view=results")
    return render(
        request,
        "public/chooser.html",
        {
            "page_bootstrap": {
                "version": 1,
                "page": "chooser",
                "requiresSession": False,
                # Presentation only; never reflect provider/account/error details.
                "entryError": request.GET.get("auth") == "unavailable",
            }
        },
    )


def public_jobs(request):
    response = PublicOpeningCollectionView.as_view()(request)
    context = {
        "directory": response.data if response.status_code == 200 else None,
        "page_bootstrap": {
            "version": 1,
            "page": "public-jobs",
            "requiresSession": False,
        },
    }
    result = render(request, "public/jobs.html", context, status=response.status_code)
    result["Cache-Control"] = "no-store"
    if response.has_header("Retry-After"):
        result["Retry-After"] = response["Retry-After"]
    return result
