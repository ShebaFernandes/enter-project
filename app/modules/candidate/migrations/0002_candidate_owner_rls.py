from django.db import migrations


DIRECT = {"candidate_candidateprofile": "identity_id"}
CHILDREN = {
    "candidate_candidatecontact": "profile_id",
    "candidate_candidateskill": "profile_id",
    "candidate_consentrecord": "profile_id",
    "candidate_employmentrecord": "profile_id",
    "candidate_profileevidence": "profile_id",
    "candidate_profilelink": "profile_id",
    "candidate_resumeasset": "profile_id",
    "candidate_visibilityrule": "profile_id",
}
RESUME_CHILDREN = {"candidate_extractedfact": "resume_id"}


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table, column in DIRECT.items():
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            cursor.execute(
                f'''CREATE POLICY candidate_owner_isolation ON "{table}"
                    USING ("{column}" = nullif(current_setting('app.identity_id', true), '')::uuid)
                    WITH CHECK ("{column}" = nullif(current_setting('app.identity_id', true), '')::uuid)'''
            )
        for table, column in CHILDREN.items():
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            # SQL identifiers come only from the fixed module-level mapping above.
            predicate = (
                f'''EXISTS (SELECT 1 FROM candidate_candidateprofile p
                    WHERE p.id = "{table}"."{column}"
                    AND p.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid)'''  # nosec B608
            )
            cursor.execute(
                f'CREATE POLICY candidate_owner_isolation ON "{table}" USING ({predicate}) WITH CHECK ({predicate})'
            )
        for table, column in RESUME_CHILDREN.items():
            cursor.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
            # SQL identifiers come only from the fixed module-level mapping above.
            predicate = (
                f'''EXISTS (SELECT 1 FROM candidate_resumeasset r
                    JOIN candidate_candidateprofile p ON p.id = r.profile_id
                    WHERE r.id = "{table}"."{column}"
                    AND p.identity_id = nullif(current_setting('app.identity_id', true), '')::uuid)'''  # nosec B608
            )
            cursor.execute(
                f'CREATE POLICY candidate_owner_isolation ON "{table}" USING ({predicate}) WITH CHECK ({predicate})'
            )


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in {*DIRECT, *CHILDREN, *RESUME_CHILDREN}:
            cursor.execute(f'DROP POLICY IF EXISTS candidate_owner_isolation ON "{table}"')
            cursor.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("candidate", "0001_initial")]
    operations = [migrations.RunPython(enable_rls, disable_rls)]
