from contextlib import contextmanager

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction

from .context import tenant_context


@contextmanager
def tenant_transaction():
    tenant_id = tenant_context.get()
    if tenant_id is None:
        raise PermissionDenied("Tenant context required")
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.tenant_id', %s, true)", [str(tenant_id)])
        yield
