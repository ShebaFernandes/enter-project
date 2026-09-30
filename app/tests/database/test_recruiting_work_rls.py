import pytest
from django.db import connection


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_phase7_recruiting_tables_have_forced_rls():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    expected = {
        "recruiting_candidateworkrecord",
        "recruiting_recruiternote",
        "recruiting_shortlistentry",
        "recruiting_recruitingstatusevent",
        "recruiting_disclosurerequest",
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT relname FROM pg_class
               WHERE relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity""",
            [list(expected)],
        )
        actual = {row[0] for row in cursor.fetchall()}
    assert actual == expected
