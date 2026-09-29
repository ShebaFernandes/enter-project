from django.db import migrations


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('ALTER TABLE "communications_notification" ENABLE ROW LEVEL SECURITY')
        cursor.execute('ALTER TABLE "communications_notification" FORCE ROW LEVEL SECURITY')
        cursor.execute(
            '''CREATE POLICY tenant_isolation ON "communications_notification"
               USING (tenant_id IS NOT NULL AND tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
               WITH CHECK (tenant_id IS NOT NULL AND tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)'''
        )


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'DROP POLICY IF EXISTS tenant_isolation ON "communications_notification"'
        )
        cursor.execute('ALTER TABLE "communications_notification" DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("communications", "0001_initial")]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
