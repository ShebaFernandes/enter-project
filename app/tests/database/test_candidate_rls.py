import uuid

import pytest
from django.db import connection, transaction

from tests.factories import CandidateProfileFactory


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_candidate_profile_rls_denies_missing_and_wrong_identity_context():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    own = CandidateProfileFactory()
    other = CandidateProfileFactory()
    role_name = f"candidate_reader_{uuid.uuid4().hex[:12]}"
    quoted = connection.ops.quote_name(role_name)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT ON candidate_candidateprofile TO {quoted}")
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {quoted}")
            cursor.execute("SELECT set_config('app.identity_id', '', true)")
            cursor.execute("SELECT count(*) FROM candidate_candidateprofile")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT set_config('app.identity_id', %s, true)", [str(own.identity_id)])
            cursor.execute("SELECT array_agg(id) FROM candidate_candidateprofile")
            assert cursor.fetchone()[0] == [own.id]
            cursor.execute(
                "SELECT set_config('app.identity_id', %s, true)", [str(other.identity_id)]
            )
            cursor.execute(
                "SELECT count(*) FROM candidate_candidateprofile WHERE id = %s", [str(own.id)]
            )
            assert cursor.fetchone()[0] == 0
            cursor.execute("RESET ROLE")
    finally:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {quoted}")
            cursor.execute(f"DROP ROLE IF EXISTS {quoted}")


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_phase3_candidate_and_privacy_tables_have_forced_rls():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    expected = {
        "candidate_candidateprofile",
        "candidate_candidatecontact",
        "candidate_candidateskill",
        "candidate_consentrecord",
        "candidate_employmentrecord",
        "candidate_profileevidence",
        "candidate_profilelink",
        "candidate_resumeasset",
        "candidate_extractedfact",
        "candidate_visibilityrule",
        "privacy_datarightsrequest",
        "privacy_legalhold",
        "privacy_activeprocessretentionexception",
        "privacy_rightsescalation",
        "privacy_rightsexport",
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT relname FROM pg_class
               WHERE relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity""",
            [list(expected)],
        )
        actual = {row[0] for row in cursor.fetchall()}
    assert actual == expected
