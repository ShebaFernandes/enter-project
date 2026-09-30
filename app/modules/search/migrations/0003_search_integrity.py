from django.db import migrations


FORWARD = r"""
ALTER TABLE search_criteriagroup ADD CONSTRAINT search_group_composite_unique UNIQUE (search_id, id);
ALTER TABLE search_criterion ADD CONSTRAINT criterion_group_same_search_fk
  FOREIGN KEY (search_id, group_id) REFERENCES search_criteriagroup (search_id, id)
  DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE search_searchdefinition ADD CONSTRAINT search_context_authoritative CHECK (
  (context_type = 'AD_HOC' AND criteria_context = '{"type":"AD_HOC"}'::jsonb AND derived_opening_id IS NULL)
  OR
  (context_type = 'OPENING'
   AND criteria_context = jsonb_build_object(
     'type', 'OPENING', 'opening_id', derived_opening_id::text
   ))
);
CREATE INDEX search_expiry_idx ON search_searchdefinition (expires_at);
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE candidate_candidateprofile NO FORCE ROW LEVEL SECURITY;
ALTER TABLE candidate_candidateskill NO FORCE ROW LEVEL SECURITY;
CREATE INDEX candidate_skill_lookup_idx ON candidate_candidateskill (normalized_name, profile_id);
CREATE INDEX candidate_role_categories_gin ON candidate_candidateprofile USING gin (role_categories jsonb_path_ops);
CREATE INDEX candidate_locations_gin ON candidate_candidateprofile USING gin (preferred_locations jsonb_path_ops);
CREATE INDEX candidate_work_arrangements_gin ON candidate_candidateprofile USING gin (work_arrangements jsonb_path_ops);
ALTER TABLE candidate_candidateprofile FORCE ROW LEVEL SECURITY;
ALTER TABLE candidate_candidateskill FORCE ROW LEVEL SECURITY;
"""
REVERSE = r"""
DROP INDEX IF EXISTS candidate_work_arrangements_gin;
DROP INDEX IF EXISTS candidate_locations_gin;
DROP INDEX IF EXISTS candidate_role_categories_gin;
DROP INDEX IF EXISTS candidate_skill_lookup_idx;
DROP INDEX IF EXISTS search_expiry_idx;
ALTER TABLE search_searchdefinition DROP CONSTRAINT IF EXISTS search_context_authoritative;
ALTER TABLE search_criterion DROP CONSTRAINT IF EXISTS criterion_group_same_search_fk;
ALTER TABLE search_criteriagroup DROP CONSTRAINT IF EXISTS search_group_composite_unique;
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for statement in FORWARD.split(";"):
            if statement.strip():
                schema_editor.execute(statement)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for statement in REVERSE.split(";"):
            if statement.strip():
                schema_editor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [("search", "0002_search_rls")]
    operations = [migrations.RunPython(forwards, backwards)]
