import uuid
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from modules.candidate.models import CandidateFinding, ConsentRecord, VisibilityRule
from modules.search.models import SearchDefinition
from modules.tenancy.models import Tenant


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_search_and_finding_tables_have_forced_rls():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    expected = {
        "search_searchdefinition",
        "search_savedsearch",
        "search_criteriagroup",
        "search_criterion",
        "search_searchresultsnapshot",
        "candidate_candidatefinding",
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT relname FROM pg_class
               WHERE relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity""",
            [list(expected)],
        )
        assert {row[0] for row in cursor.fetchall()} == expected


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_postgres_search_and_finding_rls_deny_cross_tenant(identity, tenant, profile_factory):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    other = Tenant.objects.create(
        name="Other Synthetic Company",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        legal_boundary_reference=f"contract-{uuid.uuid4()}",
        status=Tenant.Status.ACTIVE,
    )
    own_search = SearchDefinition.objects.create(
        tenant=tenant,
        actor=identity,
        context_type="AD_HOC",
        criteria_context={"type": "AD_HOC"},
    )
    SearchDefinition.objects.create(
        tenant=other,
        actor=identity,
        context_type="AD_HOC",
        criteria_context={"type": "AD_HOC"},
    )
    profile = profile_factory(published=True)
    consent = ConsentRecord.objects.create(
        profile=profile,
        purpose="RECRUITING_DISCOVERY",
        field_scope=["profile", "employment_history"],
        audience_scope={"approved_tenant_ids": [str(tenant.id)]},
        notice_version="v1",
        affirmative_action="CHECKBOX",
        source_request_id=str(uuid.uuid4()),
        expires_at=timezone.now() + timedelta(days=30),
    )
    VisibilityRule.objects.create(
        profile=profile,
        mode="APPROVED_RECRUITERS",
        approved_tenant_ids=[str(tenant.id)],
        consent_record=consent,
        actor=profile.identity,
    )
    finding = CandidateFinding.objects.create(
        profile=profile,
        code="SHORT_TENURE",
        severity="INFORMATIONAL",
        result="FOUND",
        source_record_type="EMPLOYMENT_RECORD",
        source_record_id=uuid.uuid4(),
        source_record_version=1,
        evidence={},
        message_key="candidate.finding.short_tenure",
        calculation_version="short-tenure-v1",
        evaluated_at=timezone.now(),
    )
    role_name = f"search_reader_{uuid.uuid4().hex[:12]}"
    quoted = connection.ops.quote_name(role_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(
                f"GRANT SELECT ON search_searchdefinition, candidate_candidatefinding, "
                f"candidate_candidateprofile, candidate_consentrecord TO {quoted}"
            )
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {quoted}")
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant.id)])
            cursor.execute("SELECT set_config('app.search_context_type', 'AD_HOC', true)")
            cursor.execute("SELECT id FROM search_searchdefinition")
            assert [row[0] for row in cursor.fetchall()] == [own_search.id]
            cursor.execute("SELECT id FROM candidate_candidatefinding")
            assert [row[0] for row in cursor.fetchall()] == [finding.id]
            cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(other.id)])
            cursor.execute("SELECT count(*) FROM candidate_candidatefinding")
            assert cursor.fetchone()[0] == 0
            cursor.execute("RESET ROLE")
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {quoted}")
            cursor.execute(f"DROP ROLE IF EXISTS {quoted}")
