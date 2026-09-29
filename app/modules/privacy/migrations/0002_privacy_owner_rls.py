from django.db import migrations


PROFILE_TABLES = {
    "privacy_datarightsrequest": "profile_id",
    "privacy_legalhold": "profile_id",
    "privacy_activeprocessretentionexception": "profile_id",
}
REQUEST_TABLES = {
    "privacy_rightsescalation": "request_id",
    "privacy_rightsexport": "request_id",
}


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table, column in PROFILE_TABLES.items():
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            predicate = (
                f'''EXISTS (SELECT 1 FROM candidate_candidateprofile p
                    WHERE p.id = "{table}"."{column}"
                    AND p.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid)'''
            )
            cursor.execute(
                f'CREATE POLICY privacy_owner_isolation ON "{table}" USING ({predicate}) WITH CHECK ({predicate})'
            )
        for table, column in REQUEST_TABLES.items():
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            predicate = (
                f'''EXISTS (SELECT 1 FROM privacy_datarightsrequest rr
                    JOIN candidate_candidateprofile p ON p.id = rr.profile_id
                    WHERE rr.id = "{table}"."{column}"
                    AND p.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid)'''
            )
            cursor.execute(
                f'CREATE POLICY privacy_owner_isolation ON "{table}" USING ({predicate}) WITH CHECK ({predicate})'
            )


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in {*PROFILE_TABLES, *REQUEST_TABLES}:
            cursor.execute(f'DROP POLICY IF EXISTS privacy_owner_isolation ON "{table}"')
            cursor.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("privacy", "0001_initial"), ("candidate", "0002_candidate_owner_rls")]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
