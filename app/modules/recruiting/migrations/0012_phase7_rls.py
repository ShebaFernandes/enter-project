from django.db import migrations


TABLES = (
    "recruiting_candidateworkrecord",
    "recruiting_recruiternote",
    "recruiting_shortlistentry",
    "recruiting_recruitingstatusevent",
)


def enable_phase7_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            cursor.execute(
                f'''CREATE POLICY tenant_isolation ON "{table}"
                    USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
                    WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)'''
            )
        cursor.execute('ALTER TABLE "recruiting_disclosurerequest" ENABLE ROW LEVEL SECURITY')
        cursor.execute('ALTER TABLE "recruiting_disclosurerequest" FORCE ROW LEVEL SECURITY')
        cursor.execute(
            '''CREATE POLICY disclosure_scope ON "recruiting_disclosurerequest"
               USING (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM candidate_candidateprofile profile
                   WHERE profile.id = candidate_profile_id
                     AND profile.identity_id =
                       nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )
               WITH CHECK (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM candidate_candidateprofile profile
                   WHERE profile.id = candidate_profile_id
                     AND profile.identity_id =
                       nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )'''
        )


def disable_phase7_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in TABLES:
            cursor.execute(f'DROP POLICY IF EXISTS tenant_isolation ON "{table}"')
            cursor.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
        cursor.execute(
            'DROP POLICY IF EXISTS disclosure_scope ON "recruiting_disclosurerequest"'
        )
        cursor.execute('ALTER TABLE "recruiting_disclosurerequest" DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("recruiting", "0011_remove_application_candidate_work_record_id_and_more")]
    operations = [migrations.RunPython(enable_phase7_rls, disable_phase7_rls)]
