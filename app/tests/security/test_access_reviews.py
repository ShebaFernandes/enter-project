from datetime import timedelta
from typing import cast

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.utils import timezone

from modules.audit.models import AuditEvent
from modules.identity.models import Identity, IdentityCapability
from modules.operations.concurrency import strong_etag
from modules.operations.models import OutboxEvent
from modules.tenancy.access_reviews import (
    complete_access_review,
    create_access_review,
    expire_review_exceptions,
    mark_overdue_reviews,
    populate_periodic_access_reviews,
)
from modules.tenancy.grants import request_emergency_access
from modules.tenancy.models import AccessGrant, TenantMembership
from modules.tenancy.review_models import AccessReview
from tests.factories import AccessGrantFactory, IdentityFactory, MembershipFactory

pytestmark = pytest.mark.django_db


def tenant_admin_pair(tenant):
    creator = MembershipFactory(tenant=tenant, tenant_admin=True)
    reviewer = MembershipFactory(tenant=tenant, tenant_admin=True)
    return creator, reviewer


@pytest.mark.parametrize(
    "review_type",
    ["MEMBERSHIP", "PRIVILEGED_ROLE", "PURPOSE_GRANT", "EMERGENCY_GRANT", "AUDIT_ACCESS"],
)
def test_review_population_covers_every_governance_assignment(tenant, review_type):
    creator, reviewer = tenant_admin_pair(tenant)
    MembershipFactory(tenant=tenant, recruiter=True)
    AccessGrantFactory(tenant=tenant)
    security_admin = cast(Identity, IdentityFactory())
    IdentityCapability.objects.create(
        identity=security_admin,
        role="PLATFORM_SECURITY_ADMIN",
        assigned_by=security_admin,
    )
    request_emergency_access(
        requester=security_admin,
        tenant=tenant,
        reason_code="SYNTHETIC_REVIEW",
        reason="Synthetic governance review evidence",
        incident_reference="SYN-REVIEW-1",
        object_scope={"ids": ["synthetic-object"]},
        field_scope=["profile_state"],
        operation_scope=["READ"],
        requested_minutes=30,
    )

    review = create_access_review(
        membership=creator,
        review_type=review_type,
        due_at=timezone.now() + timedelta(days=7),
        reviewer_id=reviewer.identity_id,
    )

    assert review.items.exists()
    assert review.population_hash
    assert review.reviewer_id == reviewer.identity_id
    assert "candidate" not in str(review.population_snapshot).casefold()


def test_periodic_population_creates_each_review_once_and_emits_minimized_due_events(tenant):
    creator, reviewer = tenant_admin_pair(tenant)
    MembershipFactory(tenant=tenant, recruiter=True)

    reviews = populate_periodic_access_reviews(
        membership=creator,
        due_at=timezone.now() + timedelta(days=7),
        reviewer_id=reviewer.identity_id,
    )
    repeated = populate_periodic_access_reviews(
        membership=creator,
        due_at=timezone.now() + timedelta(days=7),
        reviewer_id=reviewer.identity_id,
    )

    assert {review.review_type for review in reviews} == set(AccessReview.ReviewType.values)
    assert repeated == []
    events = OutboxEvent.objects.filter(event_type="access_review.due.v1")
    assert events.count() == len(AccessReview.ReviewType.values)
    assert all("candidate" not in str(event.payload).casefold() for event in events)


def test_review_revokes_membership_and_records_findings_and_remediation(tenant):
    creator, reviewer = tenant_admin_pair(tenant)
    target = MembershipFactory(tenant=tenant, recruiter=True)
    review = create_access_review(
        membership=creator,
        review_type="MEMBERSHIP",
        due_at=timezone.now() + timedelta(days=7),
        reviewer_id=reviewer.identity_id,
    )
    item = review.items.get(subject_id=target.identity_id)

    completed = complete_access_review(
        membership=reviewer,
        review_id=review.id,
        if_match_version=review.version,
        decisions=[
            {
                "item_id": str(item.id),
                "decision": "REVOKE",
                "finding": "Membership no longer required",
            }
        ],
    )

    target.refresh_from_db()
    item.refresh_from_db()
    assert target.status == TenantMembership.Status.REVOKED
    assert completed.state == AccessReview.State.COMPLETED
    assert item.remediation_state == "COMPLETED"
    assert completed.revocations == [str(target.id)]
    assert AuditEvent.objects.filter(action="ACCESS_REVIEW_REVOCATION").exists()


def test_purpose_and_emergency_review_revocations_take_effect(tenant):
    creator, reviewer = tenant_admin_pair(tenant)
    grant = AccessGrantFactory(tenant=tenant)
    security_admin = cast(Identity, IdentityFactory())
    IdentityCapability.objects.create(
        identity=security_admin,
        role="PLATFORM_SECURITY_ADMIN",
        assigned_by=security_admin,
    )
    emergency = request_emergency_access(
        requester=security_admin,
        tenant=tenant,
        reason_code="SYNTHETIC_REVIEW",
        reason="Synthetic emergency access review",
        incident_reference="SYN-REVIEW-2",
        object_scope={"ids": ["synthetic-object"]},
        field_scope=["profile_state"],
        operation_scope=["READ"],
        requested_minutes=30,
    )
    for review_type, source_id in [
        ("PURPOSE_GRANT", grant.id),
        ("EMERGENCY_GRANT", emergency.id),
    ]:
        review = create_access_review(
            membership=creator,
            review_type=review_type,
            due_at=timezone.now() + timedelta(days=1),
            reviewer_id=reviewer.identity_id,
        )
        review_item = review.items.get(source_object_id=str(source_id))
        complete_access_review(
            membership=reviewer,
            review_id=review.id,
            if_match_version=review.version,
            decisions=[
                {
                    "item_id": str(review_item.id),
                    "decision": "REVOKE",
                    "finding": "Access no longer required",
                }
            ],
        )
    grant.refresh_from_db()
    emergency.refresh_from_db()
    assert grant.status == AccessGrant.Status.REVOKED
    assert emergency.status == emergency.Status.REVOKED


def test_review_requires_independence_and_bounded_exception(tenant):
    creator, reviewer = tenant_admin_pair(tenant)
    review = create_access_review(
        membership=creator,
        review_type="AUDIT_ACCESS",
        due_at=timezone.now() + timedelta(days=7),
        reviewer_id=reviewer.identity_id,
    )
    own_item = review.items.get(subject_id=reviewer.identity_id)
    with pytest.raises(ValidationError):
        complete_access_review(
            membership=reviewer,
            review_id=review.id,
            if_match_version=review.version,
            decisions=[{"item_id": str(own_item.id), "decision": "RETAIN"}],
        )

    other_item = review.items.exclude(subject_id=reviewer.identity_id).first()
    assert other_item is not None
    with pytest.raises(ValidationError):
        complete_access_review(
            membership=reviewer,
            review_id=review.id,
            if_match_version=review.version,
            decisions=[{"item_id": str(other_item.id), "decision": "EXCEPTION"}],
        )

    completed = complete_access_review(
        membership=reviewer,
        review_id=review.id,
        if_match_version=review.version,
        decisions=[
            {
                "item_id": str(other_item.id),
                "decision": "EXCEPTION",
                "finding": "Temporary operational dependency",
                "exception_owner_id": str(creator.identity_id),
                "exception_expires_at": (timezone.now() + timedelta(days=1)).isoformat(),
            }
        ],
    )
    assert completed.state == AccessReview.State.COMPLETED
    other_item.refresh_from_db()
    other_item.exception_expires_at = timezone.now() - timedelta(seconds=1)
    other_item.save(update_fields=("exception_expires_at",))
    assert expire_review_exceptions() == 1
    other_item.refresh_from_db()
    assert other_item.remediation_state == "OVERDUE"


def test_overdue_and_stale_review_fail_closed(tenant):
    creator, reviewer = tenant_admin_pair(tenant)
    review = create_access_review(
        membership=creator,
        review_type="MEMBERSHIP",
        due_at=timezone.now() - timedelta(seconds=1),
        reviewer_id=reviewer.identity_id,
    )
    assert mark_overdue_reviews() == 1
    review.refresh_from_db()
    assert review.state == AccessReview.State.OVERDUE
    with pytest.raises(ValidationError):
        complete_access_review(
            membership=reviewer,
            review_id=review.id,
            if_match_version=review.version + 1,
            decisions=[],
        )


def test_only_tenant_admin_can_create_or_complete_tenant_review(tenant):
    recruiter = MembershipFactory(tenant=tenant, recruiter=True)
    with pytest.raises(PermissionDenied):
        create_access_review(
            membership=recruiter,
            review_type="MEMBERSHIP",
            due_at=timezone.now() + timedelta(days=1),
        )


def test_access_review_api_rejects_stale_completion(api_client, tenant):
    creator, _ = tenant_admin_pair(tenant)
    target = MembershipFactory(tenant=tenant, recruiter=True)
    review = create_access_review(
        membership=creator,
        review_type="MEMBERSHIP",
        due_at=timezone.now() + timedelta(days=1),
    )
    review_item = review.items.get(subject_id=target.identity_id)
    api_client.force_login(creator.identity)
    response = api_client.post(
        f"/api/v1/tenants/{tenant.id}/access-reviews/{review.id}/complete",
        {"decisions": [{"item_id": str(review_item.id), "decision": "RETAIN"}]},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
        HTTP_IF_MATCH=strong_etag(review.id, review.version + 1),
        HTTP_IDEMPOTENCY_KEY="phase9-stale-access-review",
    )
    assert response.status_code == 409
    assert response.data["current"]["version"] == review.version


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_access_review_tables_have_forced_rls():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    expected = {"tenancy_accessreview", "tenancy_accessreviewitem"}
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT relname FROM pg_class
               WHERE relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity""",
            [list(expected)],
        )
        assert {row[0] for row in cursor.fetchall()} == expected
