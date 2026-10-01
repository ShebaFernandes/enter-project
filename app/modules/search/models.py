import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .handoff_models import SearchWorkflowHandoff  # noqa: F401


def expires_in_seven_days():
    return timezone.now() + timedelta(days=7)


class SearchDefinition(models.Model):
    class ContextType(models.TextChoices):
        AD_HOC = "AD_HOC"
        OPENING = "OPENING"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="searches")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    prompt = models.TextField(max_length=4000, blank=True)
    context_type = models.CharField(max_length=10, choices=ContextType)
    criteria_context = models.JSONField()
    derived_opening = models.ForeignKey(
        "recruiting.Opening", on_delete=models.PROTECT, null=True, blank=True, editable=False
    )
    result_limit = models.PositiveSmallIntegerField(default=25)
    expires_at = models.DateTimeField(default=expires_in_seven_days)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(context_type="AD_HOC", derived_opening__isnull=True)
                    | Q(context_type="OPENING", derived_opening__isnull=False)
                ),
                name="search_context_opening_shape",
            ),
            models.CheckConstraint(
                condition=Q(result_limit__gte=1, result_limit__lte=100),
                name="search_result_limit_range",
            ),
        ]
        indexes = [models.Index(fields=("tenant", "actor", "created_at"))]

    def clean(self):
        expected = {"type": self.context_type}
        if self.context_type == self.ContextType.OPENING:
            expected["opening_id"] = str(self.derived_opening_id)
        if self.criteria_context != expected:
            raise ValidationError(
                {"criteria_context": "Context must equal the server-derived opening context."}
            )
        if (
            self.derived_opening_id
            and self.derived_opening is not None
            and self.derived_opening.tenant_id != self.tenant_id
        ):
            raise ValidationError({"derived_opening": "Opening must belong to the search tenant."})


class CriteriaGroup(models.Model):
    class Purpose(models.TextChoices):
        REQUIREMENT = "REQUIREMENT"
        PREFERENCE = "PREFERENCE"
        EXCLUSION = "EXCLUSION"

    class Operator(models.TextChoices):
        ANY = "ANY"
        ALL = "ALL"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stable_id = models.UUIDField()
    search = models.ForeignKey(SearchDefinition, on_delete=models.CASCADE, related_name="groups")
    purpose = models.CharField(max_length=20, choices=Purpose)
    operator = models.CharField(max_length=3, choices=Operator)
    label = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("search", "stable_id"), name="uniq_search_group")
        ]


class Criterion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stable_id = models.UUIDField()
    search = models.ForeignKey(SearchDefinition, on_delete=models.CASCADE, related_name="criteria")
    group = models.ForeignKey(CriteriaGroup, on_delete=models.CASCADE, related_name="criteria")
    field = models.CharField(max_length=100)
    operator = models.CharField(max_length=20)
    value = models.JSONField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("search", "stable_id"), name="uniq_search_criterion")
        ]

    def clean(self):
        if self.group_id and self.search_id and self.group.search_id != self.search_id:
            raise ValidationError({"group": "Criterion group must belong to the same search."})


class SearchResultSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search = models.ForeignKey(SearchDefinition, on_delete=models.CASCADE, related_name="results")
    candidate_profile_id = models.UUIDField()
    ordinal = models.PositiveIntegerField()
    score = models.DecimalField(max_digits=8, decimal_places=3)
    evidence = models.JSONField(default=list)
    unknowns = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("search", "candidate_profile_id"), name="uniq_search_candidate_result"
            ),
            models.UniqueConstraint(
                fields=("search", "ordinal"), name="uniq_search_result_ordinal"
            ),
        ]


class SavedSearch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    search = models.OneToOneField(SearchDefinition, on_delete=models.CASCADE, related_name="saved")
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    result_context_snapshot = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "actor", "name"), name="uniq_actor_saved_search_name"
            )
        ]

    def clean(self):
        if self.search_id and (
            self.search.tenant_id != self.tenant_id or self.search.actor_id != self.actor_id
        ):
            raise ValidationError(
                {"search": "Saved searches must reference their owner's tenant-scoped search."}
            )
