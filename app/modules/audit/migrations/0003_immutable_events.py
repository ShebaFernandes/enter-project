from django.db import migrations


def create_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                """
                CREATE FUNCTION prevent_audit_event_mutation() RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'audit events are immutable';
                END;
                $$ LANGUAGE plpgsql;
                CREATE TRIGGER audit_event_no_update_delete
                BEFORE UPDATE OR DELETE ON audit_auditevent
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation();
                """
            )


def remove_guards(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute("DROP TRIGGER IF EXISTS audit_event_no_update_delete ON audit_auditevent")
            cursor.execute("DROP FUNCTION IF EXISTS prevent_audit_event_mutation()")


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_initial")]
    operations = [migrations.RunPython(create_guards, remove_guards)]
