from django.db import migrations


def enable_application_disclosure(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        r"""
        CREATE OR REPLACE FUNCTION candidate_application_visible(candidate_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public SET row_security = off AS $$
          SELECT EXISTS (
            SELECT 1
            FROM public.recruiting_application application
            JOIN public.candidate_consentrecord consent
              ON consent.id = application.consent_context_id
            WHERE application.candidate_profile_id = candidate_id
              AND application.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
              AND application.state IN ('SUBMITTED', 'ACTIVE')
              AND consent.profile_id = candidate_id
              AND consent.purpose = 'APPLICATION_SUBMISSION'
              AND consent.withdrawn_at IS NULL
              AND consent.expires_at > now()
              AND consent.field_scope @> '["application"]'::jsonb
              AND consent.audience_scope->>'tenant_id' = application.tenant_id::text
              AND consent.audience_scope->>'opening_id' = application.opening_id::text
          )
        $$;

        CREATE OR REPLACE FUNCTION candidate_application_consent_visible(
          candidate_id uuid, consent_id uuid
        ) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, public SET row_security = off AS $$
          SELECT candidate_application_visible(candidate_id)
            AND EXISTS (
              SELECT 1 FROM public.recruiting_application application
              WHERE application.consent_context_id = consent_id
                AND application.candidate_profile_id = candidate_id
                AND application.tenant_id =
                  nullif(current_setting('app.tenant_id', true), '')::uuid
            )
        $$;

        CREATE POLICY applicant_scope ON candidate_candidateprofile FOR SELECT
        USING (candidate_application_visible(id));

        CREATE POLICY applicant_scope ON candidate_consentrecord FOR SELECT
        USING (candidate_application_consent_visible(profile_id, id));

        CREATE POLICY applicant_scope ON candidate_candidatecontact FOR SELECT
        USING (candidate_application_visible(profile_id));
        """
    )


def disable_application_disclosure(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DROP POLICY IF EXISTS applicant_scope ON candidate_candidatecontact;
        DROP POLICY IF EXISTS applicant_scope ON candidate_consentrecord;
        DROP POLICY IF EXISTS applicant_scope ON candidate_candidateprofile;
        DROP FUNCTION IF EXISTS candidate_application_consent_visible(uuid, uuid);
        DROP FUNCTION IF EXISTS candidate_application_visible(uuid);
        """
    )


class Migration(migrations.Migration):
    dependencies = [("recruiting", "0009_immutable_application_submission")]
    operations = [
        migrations.RunPython(enable_application_disclosure, disable_application_disclosure)
    ]
