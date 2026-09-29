from django.db import migrations


DIRECT_TABLES = {
    "recruiting_application": "tenant_id",
    "recruiting_applicationstatusevent": "tenant_id",
    "recruiting_recruiterenteredcandidate": "tenant_id",
}


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table, column in DIRECT_TABLES.items():
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            cursor.execute(
                f'''CREATE POLICY tenant_isolation ON "{table}"
                    USING ("{column}" = nullif(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK ("{column}" = nullif(current_setting('app.tenant_id', true), '')::uuid)'''
            )
        cursor.execute('ALTER TABLE "recruiting_hiringteammember" ENABLE ROW LEVEL SECURITY')
        cursor.execute('ALTER TABLE "recruiting_hiringteammember" FORCE ROW LEVEL SECURITY')
        cursor.execute(
            '''CREATE POLICY tenant_isolation ON "recruiting_hiringteammember"
               USING (EXISTS (
                   SELECT 1 FROM recruiting_opening opening
                   WHERE opening.id = opening_id
                     AND opening.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
               ))
               WITH CHECK (EXISTS (
                   SELECT 1 FROM recruiting_opening opening
                   WHERE opening.id = opening_id
                     AND opening.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
               ))'''
        )


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in (*DIRECT_TABLES, "recruiting_hiringteammember"):
            cursor.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
            cursor.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("recruiting", "0002_application_applicationstatusevent_and_more")]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
