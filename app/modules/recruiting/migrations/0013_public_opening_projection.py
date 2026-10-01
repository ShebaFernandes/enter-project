import uuid

import django.db.models.deletion
from django.db import migrations, models


def secure_projection(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        raise RuntimeError("Public publication requires PostgreSQL RLS")
    schema_editor.execute(
        """
        DO $$
        DECLARE role_name text;
        BEGIN
          FOREACH role_name IN ARRAY ARRAY[
            'enter_public_openings_reader', 'enter_opening_publisher'
          ] LOOP
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
              EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS', role_name);
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name
                       AND (rolsuper OR rolbypassrls OR rolcanlogin)) THEN
              RAISE EXCEPTION 'Unsafe publication role configuration';
            END IF;
            EXECUTE format('GRANT %I TO %I', role_name, current_user);
          END LOOP;
        END $$;

        GRANT USAGE ON SCHEMA public TO enter_public_openings_reader, enter_opening_publisher;
        REVOKE ALL ON recruiting_publicopeningprojection FROM PUBLIC;
        REVOKE ALL ON recruiting_openingpublicationlink FROM PUBLIC;
        GRANT SELECT ON recruiting_publicopeningprojection TO enter_public_openings_reader;
        GRANT SELECT, INSERT, UPDATE, DELETE ON recruiting_publicopeningprojection,
          recruiting_openingpublicationlink TO enter_opening_publisher;

        ALTER TABLE recruiting_publicopeningprojection ENABLE ROW LEVEL SECURITY;
        ALTER TABLE recruiting_publicopeningprojection FORCE ROW LEVEL SECURITY;
        ALTER TABLE recruiting_openingpublicationlink ENABLE ROW LEVEL SECURITY;
        ALTER TABLE recruiting_openingpublicationlink FORCE ROW LEVEL SECURITY;

        CREATE POLICY public_published_read ON recruiting_publicopeningprojection
          FOR SELECT TO enter_public_openings_reader
          USING (active AND published_at <= statement_timestamp()
                 AND (closes_at IS NULL OR closes_at > statement_timestamp()));
        CREATE POLICY publication_writer ON recruiting_publicopeningprojection
          TO enter_opening_publisher
          USING (EXISTS (SELECT 1 FROM recruiting_openingpublicationlink link
                         WHERE link.public_id = id
                           AND link.tenant_id =
                             nullif(current_setting('app.tenant_id', true), '')::uuid))
          WITH CHECK (EXISTS (SELECT 1 FROM recruiting_openingpublicationlink link
                         WHERE link.public_id = id
                           AND link.tenant_id =
                             nullif(current_setting('app.tenant_id', true), '')::uuid));
        CREATE POLICY publication_link_tenant ON recruiting_openingpublicationlink
          TO enter_opening_publisher
          USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
          WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);
        CREATE POLICY publication_link_application_resolution ON recruiting_openingpublicationlink
          FOR SELECT TO enter_opening_publisher
          USING (public_id = nullif(current_setting('app.public_opening_id', true), '')::uuid);

        CREATE FUNCTION invalidate_opening_publication() RETURNS trigger
          LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public AS $$
        BEGIN
          UPDATE public.recruiting_publicopeningprojection SET active = false
            WHERE id IN (SELECT public_id FROM public.recruiting_openingpublicationlink
                         WHERE opening_id = OLD.id);
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER invalidate_publication_before_source_change
          BEFORE UPDATE OR DELETE ON recruiting_opening FOR EACH ROW
          EXECUTE FUNCTION invalidate_opening_publication();
        CREATE FUNCTION invalidate_deleted_publication_link() RETURNS trigger
          LANGUAGE plpgsql SECURITY INVOKER SET search_path = pg_catalog, public AS $$
        BEGIN
          UPDATE public.recruiting_publicopeningprojection SET active = false
            WHERE id = OLD.public_id;
          RETURN OLD;
        END $$;
        CREATE TRIGGER invalidate_publication_before_link_delete
          BEFORE DELETE ON recruiting_openingpublicationlink FOR EACH ROW
          EXECUTE FUNCTION invalidate_deleted_publication_link();
        """,
        params=None,
    )


def unsecure_projection(apps, schema_editor):
    schema_editor.execute(
        """
        DROP TRIGGER invalidate_publication_before_source_change ON recruiting_opening;
        DROP FUNCTION invalidate_opening_publication();
        DROP TRIGGER invalidate_publication_before_link_delete ON recruiting_openingpublicationlink;
        DROP FUNCTION invalidate_deleted_publication_link();
        DROP POLICY publication_link_tenant ON recruiting_openingpublicationlink;
        DROP POLICY publication_link_application_resolution ON recruiting_openingpublicationlink;
        DROP POLICY publication_writer ON recruiting_publicopeningprojection;
        DROP POLICY public_published_read ON recruiting_publicopeningprojection;
        """
    )
    # Cluster roles may be shared with another database. Never drop them on rollback.


class Migration(migrations.Migration):
    dependencies = [("recruiting", "0012_phase7_rls")]
    operations = [
        migrations.CreateModel(
            name="PublicOpeningProjection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=300)),
                ("description", models.TextField(blank=True, max_length=20000)),
                ("location", models.CharField(blank=True, max_length=300)),
                ("work_mode", models.CharField(choices=[("REMOTE", "Remote"), ("HYBRID", "Hybrid"), ("ON_SITE", "On Site"), ("FLEXIBLE", "Flexible")], max_length=20)),
                ("employment_type", models.CharField(max_length=100)),
                ("published_at", models.DateTimeField()),
                ("closes_at", models.DateTimeField(blank=True, null=True)),
                ("active", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="OpeningPublicationLink",
            fields=[
                ("opening", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to="recruiting.opening")),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="tenancy.tenant")),
            ],
        ),
        migrations.RunPython(secure_projection, unsecure_projection),
    ]
