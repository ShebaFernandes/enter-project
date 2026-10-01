from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from pydantic import ValidationError as SchemaError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from modules.operations.concurrency import require_if_match

from . import handoffs
from .eligibility import eligible_profiles
from .engine import evaluate_candidate, validate_criteria
from .models import SearchDefinition
from .query import search_authorization_context
from .saved_searches import _criteria
from .views import _candidate_values, _membership, _result


class HandoffThrottle(SimpleRateThrottle):
    rate = "60/min"

    def get_cache_key(self, request, view):
        return f"handoff:{request.user.pk}:{self.get_ident(request)}"


class PrivateView(APIView):
    throttle_classes = [HandoffThrottle]

    def initial(self, request, *args, **kwargs):
        if not settings.SEARCH_WORKFLOW_HANDOFF_ENABLED:
            raise Http404
        super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        response["Referrer-Policy"] = "no-referrer"
        return response


class HandoffView(PrivateView):
    def get(self, request, tenant_id, kind):
        item, payload, membership = handoffs.restore(request, tenant_id, kind)
        handoffs.audit(item, membership, "RESTORED")
        return Response(handoffs.metadata(item, payload, membership))

    def post(self, request, tenant_id, kind):
        try:
            result, created = handoffs.create(request, tenant_id, kind)
        except SchemaError:
            raise ValidationError("Invalid structured criteria.") from None
        return Response(result, status=201 if created else 200)

    def patch(self, request, tenant_id, kind):
        try:
            result = handoffs.revise(request, tenant_id, kind)
        except SchemaError:
            raise ValidationError("Invalid structured criteria.") from None
        return Response(result)

    @transaction.atomic
    def delete(self, request, tenant_id, kind):
        item, _, membership = handoffs.restore(request, tenant_id, kind, lock=True)
        require_if_match(request.headers.get("If-Match"), item, {})
        item.state = "REVOKED"
        item.version += 1
        item.save(update_fields=["state", "version"])
        handoffs.audit(item, membership, "REVOKED")
        return Response(status=204)


class HandoffDisplayView(PrivateView):
    """Separate authorized candidate read, never part of restoring workflow metadata.

    Projects only the already persisted result set, freshly checking eligibility,
    consent and fields. No search execution, new run, ranking or result-copy writes.
    """

    def get(self, request, tenant_id):
        item, _, membership = handoffs.restore(request, tenant_id, "search-results")
        search = item.search
        criteria = _criteria(search)
        groups = validate_criteria(criteria["groups"], criteria["criteria"])
        snapshots = list(search.results.order_by("ordinal"))
        with search_authorization_context(search.criteria_context):
            profiles = {
                str(p.pk): p
                for p in eligible_profiles(membership, search.criteria_context)
                .filter(pk__in=[s.candidate_profile_id for s in snapshots])
                .prefetch_related("skills", "consents", "findings")
            }
            items = []
            for snapshot in snapshots:
                profile = profiles.get(str(snapshot.candidate_profile_id))
                if profile is None:
                    continue
                matched = evaluate_candidate(_candidate_values(profile), groups)
                if matched.eligible:
                    items.append(_result(profile, matched, membership))
        return Response({"search_id": str(search.pk), "items": items, "next_cursor": None})


class ComparisonReturnView(PrivateView):
    """Issue a separate results bearer; never accept or persist a client return URL."""

    @transaction.atomic
    def post(self, request, tenant_id):
        if request.data:
            raise ValidationError("Return navigation does not accept a payload.")
        item, _, _ = handoffs.restore(request, tenant_id, "comparison-selection", lock=True)
        result, _ = handoffs.create(
            request,
            tenant_id,
            "search-results",
            internal_body={"search_id": str(item.search_id)},
            expires_at=item.expires_at,
        )
        return Response(
            {
                "return_path": (
                    f"/tenants/{tenant_id}/recruiter/search/?view=results"
                    f"#handoff={result['token']}"
                    f"&selection={request.headers['X-Workflow-Handoff']}"
                )
            }
        )


class RecentSearchView(PrivateView):
    def get(self, request, tenant_id, search_id=None):
        membership = _membership(request, tenant_id)
        recent = SearchDefinition.objects.filter(
            tenant_id=tenant_id,
            actor=membership.identity,
            context_type="AD_HOC",
            saved__isnull=True,
            expires_at__gt=timezone.now(),
        ).order_by("-created_at", "-id")[:6]
        items = [
            {
                "search_id": str(s.pk),
                "prompt": s.prompt,
                "criteria": _criteria(s),
                "created_at": s.created_at,
                "expires_at": s.expires_at,
            }
            for s in recent
        ]
        if search_id is None:
            return Response(items)
        item = next((s for s in items if s["search_id"] == str(search_id)), None)
        if item is None:
            raise Http404
        return Response(item)
