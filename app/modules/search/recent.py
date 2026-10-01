"""Bound the recent projection without destroying recruiting provenance."""

from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from modules.recruiting.models import CandidateWorkRecord

from .models import SearchDefinition
from .saved_searches import _authorize


@transaction.atomic
def maintain_recent_searches(*, membership) -> None:
    _authorize(membership)
    now = timezone.now()
    owned = SearchDefinition.objects.filter(
        tenant_id=membership.tenant_id,
        actor=membership.identity,
        context_type=SearchDefinition.ContextType.AD_HOC,
        saved__isnull=True,
    )
    # A visible-list eviction must not invalidate an active, session-bound journey.
    from .models import SearchWorkflowHandoff

    active_ids = SearchWorkflowHandoff.objects.filter(
        tenant_id=membership.tenant_id,
        actor=membership.identity,
        state="ACTIVE",
        expires_at__gt=now,
        search_id__isnull=False,
    ).values_list("search_id", flat=True)
    owned = owned.exclude(pk__in=active_ids)
    # expires_at bounds recent presentation, not the lifetime of provenance.
    keep = list(
        owned.filter(expires_at__gt=now)
        .order_by("-created_at", "-id")
        .values_list("id", flat=True)[:6]
    )
    owned.exclude(id__in=keep).filter(expires_at__gt=now).update(expires_at=now)
    for search in owned.filter(expires_at__lte=now).select_for_update(of=("self",)):
        if CandidateWorkRecord.objects.filter(originating_search_id=search.id).exists():
            continue
        if hasattr(search, "saved"):
            continue
        try:
            # Retain PROTECT; a concurrent provenance reference wins.
            with transaction.atomic():
                search.delete()
        except ProtectedError:
            continue
