import pytest
from django.core.exceptions import PermissionDenied

from modules.tenancy.context import tenant_context
from modules.tenancy.rls import tenant_transaction


def test_missing_tenant_context_fails_closed():
    token = tenant_context.set(None)
    try:
        with pytest.raises(PermissionDenied), tenant_transaction():
            pass
    finally:
        tenant_context.reset(token)


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_postgres_rls_uses_transaction_local_context(tenant):
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")
    token = tenant_context.set(tenant.id)
    try:
        with tenant_transaction(), connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            assert cursor.fetchone()[0] == str(tenant.id)
    finally:
        tenant_context.reset(token)
