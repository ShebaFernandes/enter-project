from django.db import migrations


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        r"""
        CREATE OR REPLACE FUNCTION candidate_search_visible(candidate_id uuid)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET row_security = off AS $$
          SELECT EXISTS (
            SELECT 1
            FROM candidate_candidateprofile p
            JOIN candidate_visibilityrule vr ON vr.profile_id = p.id AND vr.superseded_at IS NULL
            JOIN candidate_consentrecord cr ON cr.id = vr.consent_record_id
            WHERE p.id = candidate_id
              AND p.profile_state = 'PUBLISHED'
              AND cr.purpose = 'RECRUITING_DISCOVERY'
              AND cr.withdrawn_at IS NULL AND cr.expires_at > now()
              AND cr.field_scope @> '["profile"]'::jsonb
              AND nullif(current_setting('app.tenant_id', true), '') IS NOT NULL
              AND (
                (current_setting('app.search_context_type', true) = 'AD_HOC'
                 AND vr.mode = 'APPROVED_RECRUITERS'
                 AND vr.approved_tenant_ids @> jsonb_build_array(current_setting('app.tenant_id', true))
                 AND COALESCE(cr.audience_scope->'approved_tenant_ids', '[]'::jsonb)
                     @> jsonb_build_array(current_setting('app.tenant_id', true)))
                OR
                (current_setting('app.search_context_type', true) = 'OPENING'
                 AND vr.mode = 'MATCHING_ROLES'
                 AND EXISTS (
                   SELECT 1 FROM recruiting_opening o
                   WHERE o.id = nullif(current_setting('app.search_opening_id', true), '')::uuid
                     AND o.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
                     AND o.state = 'OPEN'
                     AND COALESCE(vr.matching_preferences->'role_categories', p.role_categories)
                         @> jsonb_build_array(lower(o.title))
                     AND COALESCE(vr.matching_preferences->'preferred_locations', p.preferred_locations)
                         @> jsonb_build_array(lower(COALESCE(o.location->>'normalized', o.location->>'display', o.location->>'city', '')))
                     AND COALESCE(vr.matching_preferences->'work_arrangements', p.work_arrangements)
                         @> jsonb_build_array(o.work_mode)
                 ))
              )
          )
        $$;

        DROP POLICY IF EXISTS recruiter_discovery ON candidate_candidatefinding;
        CREATE POLICY recruiter_discovery ON candidate_candidatefinding FOR SELECT
        USING (candidate_search_visible(profile_id) AND result = 'FOUND' AND superseded_at IS NULL
          AND EXISTS (SELECT 1 FROM candidate_consentrecord cr
            WHERE cr.profile_id = candidate_candidatefinding.profile_id
              AND cr.purpose = 'RECRUITING_DISCOVERY' AND cr.withdrawn_at IS NULL
              AND cr.expires_at > now()
              AND cr.field_scope @> '["employment_history"]'::jsonb));
        """
    )


class Migration(migrations.Migration):
    dependencies = [("candidate", "0005_candidate_finding_rls")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
