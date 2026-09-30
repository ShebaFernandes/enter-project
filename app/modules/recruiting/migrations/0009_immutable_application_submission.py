from django.db import migrations


def protect_submission_time(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            '''CREATE FUNCTION protect_application_submission_time() RETURNS trigger AS $$
               BEGIN
                 IF OLD.submitted_at IS NOT NULL
                    AND NEW.submitted_at IS DISTINCT FROM OLD.submitted_at THEN
                   RAISE EXCEPTION 'application submitted_at is immutable';
                 END IF;
                 RETURN NEW;
               END;
               $$ LANGUAGE plpgsql'''
        )
        cursor.execute(
            '''CREATE TRIGGER application_submission_time_immutable
               BEFORE UPDATE ON recruiting_application
               FOR EACH ROW EXECUTE FUNCTION protect_application_submission_time()'''
        )


def unprotect_submission_time(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "DROP TRIGGER IF EXISTS application_submission_time_immutable ON recruiting_application"
        )
        cursor.execute("DROP FUNCTION IF EXISTS protect_application_submission_time()")


class Migration(migrations.Migration):
    dependencies = [("recruiting", "0008_remove_application_consent_context_id_and_more")]
    operations = [migrations.RunPython(protect_submission_time, unprotect_submission_time)]
