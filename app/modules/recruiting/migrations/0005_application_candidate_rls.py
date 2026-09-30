from django.db import migrations


def enable_candidate_application_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP POLICY IF EXISTS tenant_isolation ON "recruiting_application"')
        cursor.execute(
            '''CREATE POLICY application_scope ON "recruiting_application"
               USING (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM candidate_candidateprofile profile
                   WHERE profile.id = candidate_profile_id
                     AND profile.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )
               WITH CHECK (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM candidate_candidateprofile profile
                   WHERE profile.id = candidate_profile_id
                     AND profile.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )'''
        )
        cursor.execute(
            'DROP POLICY IF EXISTS tenant_isolation ON "recruiting_applicationstatusevent"'
        )
        cursor.execute(
            '''CREATE POLICY application_history_scope ON "recruiting_applicationstatusevent"
               USING (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM recruiting_application application
                   JOIN candidate_candidateprofile profile
                     ON profile.id = application.candidate_profile_id
                   WHERE application.id = application_id
                     AND profile.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )
               WITH CHECK (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM recruiting_application application
                   JOIN candidate_candidateprofile profile
                     ON profile.id = application.candidate_profile_id
                   WHERE application.id = application_id
                     AND profile.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )'''
        )
        cursor.execute('ALTER TABLE "recruiting_applicationstatuspreview" ENABLE ROW LEVEL SECURITY')
        cursor.execute('ALTER TABLE "recruiting_applicationstatuspreview" FORCE ROW LEVEL SECURITY')
        cursor.execute(
            '''CREATE POLICY tenant_isolation ON "recruiting_applicationstatuspreview"
               USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
               WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)'''
        )
        cursor.execute('DROP POLICY IF EXISTS tenant_isolation ON "communications_notification"')
        cursor.execute(
            '''CREATE POLICY notification_scope ON "communications_notification"
               USING (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM candidate_candidateprofile profile
                   WHERE profile.id = candidate_profile_id
                     AND profile.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )
               WITH CHECK (
                 tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                 OR EXISTS (
                   SELECT 1 FROM candidate_candidateprofile profile
                   WHERE profile.id = candidate_profile_id
                     AND profile.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid
                 )
               )'''
        )


def restore_tenant_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table, policy in (
            ("recruiting_application", "application_scope"),
            ("recruiting_applicationstatusevent", "application_history_scope"),
            ("recruiting_applicationstatuspreview", "tenant_isolation"),
            ("communications_notification", "notification_scope"),
        ):
            cursor.execute(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"')
        cursor.execute('ALTER TABLE "recruiting_applicationstatuspreview" DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [
        ("recruiting", "0004_application_candidate_work_record_id_and_more"),
        ("communications", "0003_notification_notification_attempts_max_5"),
    ]
    operations = [migrations.RunPython(enable_candidate_application_rls, restore_tenant_rls)]
