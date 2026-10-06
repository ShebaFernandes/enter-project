from django.db import migrations


def enable_applicant_review(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        r'''
        CREATE OR REPLACE FUNCTION candidate_application_field_visible(
            candidate_id uuid, requested_field text
        ) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
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
              AND consent.field_scope @> jsonb_build_array(requested_field)
              AND consent.audience_scope->>'tenant_id' = application.tenant_id::text
              AND consent.audience_scope->>'opening_id' = application.opening_id::text
          )
        $$;

        CREATE POLICY applicant_scope ON candidate_candidateskill FOR SELECT
          USING (candidate_application_field_visible(profile_id, 'profile'));
        CREATE POLICY applicant_scope ON candidate_profilelink FOR SELECT
          USING (candidate_application_field_visible(profile_id, 'professional_links'));
        CREATE POLICY applicant_scope ON candidate_employmentrecord FOR SELECT
          USING (candidate_application_field_visible(profile_id, 'employment_history'));
        CREATE POLICY applicant_scope ON candidate_resumeasset FOR SELECT
          USING (candidate_application_field_visible(profile_id, 'resume'));
        CREATE POLICY applicant_scope ON candidate_extractedfact FOR SELECT
          USING (candidate_application_field_visible(
            (SELECT profile_id FROM candidate_resumeasset WHERE id = resume_id), 'resume'
          ));
        '''
    )


def disable_applicant_review(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DROP POLICY IF EXISTS applicant_scope ON candidate_extractedfact;
        DROP POLICY IF EXISTS applicant_scope ON candidate_resumeasset;
        DROP POLICY IF EXISTS applicant_scope ON candidate_employmentrecord;
        DROP POLICY IF EXISTS applicant_scope ON candidate_profilelink;
        DROP POLICY IF EXISTS applicant_scope ON candidate_candidateskill;
        DROP FUNCTION IF EXISTS candidate_application_field_visible(uuid, text);
        """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("recruiting", "0014_publication_version"),
        ("candidate", "0007_candidateprofile_education"),
    ]
    operations = [migrations.RunPython(enable_applicant_review, disable_applicant_review)]
