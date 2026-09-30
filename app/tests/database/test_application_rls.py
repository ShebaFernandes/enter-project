import uuid

import pytest
from django.db import connection, transaction
from django.db.utils import DatabaseError
from django.utils import timezone

from tests.factories import ApplicationFactory, CandidateProfileFactory, OpeningFactory


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_application_rls_allows_exact_candidate_or_tenant_and_denies_cross_scope():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    owner = CandidateProfileFactory()
    other = CandidateProfileFactory()
    application = ApplicationFactory(
        opening=OpeningFactory(open=True), candidate_profile_id=owner.id, submitted=True
    )
    role_name = f"application_reader_{uuid.uuid4().hex[:12]}"
    quoted = connection.ops.quote_name(role_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT ON recruiting_application TO {quoted}")
            cursor.execute(f"GRANT SELECT ON candidate_candidateprofile TO {quoted}")
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {quoted}")
            cursor.execute("SELECT set_config('app.tenant_id', '', true)")
            cursor.execute(
                "SELECT set_config('app.identity_id', %s, true)", [str(owner.identity_id)]
            )
            cursor.execute("SELECT array_agg(id) FROM recruiting_application")
            assert cursor.fetchone()[0] == [application.id]
            cursor.execute(
                "SELECT set_config('app.identity_id', %s, true)", [str(other.identity_id)]
            )
            cursor.execute("SELECT count(*) FROM recruiting_application")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT set_config('app.identity_id', '', true)")
            cursor.execute(
                "SELECT set_config('app.tenant_id', %s, true)", [str(application.tenant_id)]
            )
            cursor.execute("SELECT array_agg(id) FROM recruiting_application")
            assert cursor.fetchone()[0] == [application.id]
            cursor.execute("RESET ROLE")
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {quoted}")
            cursor.execute(f"DROP ROLE IF EXISTS {quoted}")


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_phase6_application_tables_have_forced_rls():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    expected = {
        "recruiting_application",
        "recruiting_applicationstatusevent",
        "recruiting_applicationstatuspreview",
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT relname FROM pg_class
               WHERE relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity""",
            [list(expected)],
        )
        actual = {row[0] for row in cursor.fetchall()}
    assert actual == expected


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_submitted_application_timestamp_is_database_immutable():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    application = ApplicationFactory(submitted=True)
    with pytest.raises(DatabaseError), transaction.atomic():
        type(application).objects.filter(pk=application.pk).update(submitted_at=timezone.now())
