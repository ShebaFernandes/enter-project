from django.db import migrations


TENANT_TABLES = {
    "tenancy_businessunit": "tenant_id",
    "tenancy_tenantmembership": "tenant_id",
    "tenancy_accessgrant": "tenant_id",
    "tenancy_emergencyaccessrequest": "tenant_id",
    "recruiting_opening": "tenant_id",
}


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table, column in TENANT_TABLES.items():
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            cursor.execute(
                f'''CREATE POLICY tenant_isolation ON "{table}"
                    USING ("{column}" = nullif(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK ("{column}" = nullif(current_setting('app.tenant_id', true), '')::uuid)'''
            )


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in TENANT_TABLES:
            cursor.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
            cursor.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0001_initial"), ("recruiting", "0001_initial")]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
