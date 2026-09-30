from django.db import migrations


SQL = r"""
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'search_criteriagroup'
      AND column_name = 'stable_id'
  ) THEN
    ALTER TABLE search_criteriagroup ADD COLUMN stable_id uuid;
    UPDATE search_criteriagroup SET stable_id = id;
    ALTER TABLE search_criteriagroup ALTER COLUMN stable_id SET NOT NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'search_criterion'
      AND column_name = 'stable_id'
  ) THEN
    ALTER TABLE search_criterion ADD COLUMN stable_id uuid;
    UPDATE search_criterion SET stable_id = id;
    ALTER TABLE search_criterion ALTER COLUMN stable_id SET NOT NULL;
  END IF;
END $$;

ALTER TABLE search_criterion DROP CONSTRAINT IF EXISTS criterion_group_same_search_fk;
ALTER TABLE search_criteriagroup DROP CONSTRAINT IF EXISTS uniq_search_group;
ALTER TABLE search_criterion DROP CONSTRAINT IF EXISTS uniq_search_criterion;
ALTER TABLE search_criteriagroup
  ADD CONSTRAINT uniq_search_group UNIQUE (search_id, stable_id);
ALTER TABLE search_criterion
  ADD CONSTRAINT uniq_search_criterion UNIQUE (search_id, stable_id);
ALTER TABLE search_criterion ADD CONSTRAINT criterion_group_same_search_fk
  FOREIGN KEY (search_id, group_id) REFERENCES search_criteriagroup (search_id, id)
  DEFERRABLE INITIALLY DEFERRED;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE candidate_candidateprofile NO FORCE ROW LEVEL SECURITY;
ALTER TABLE candidate_candidateskill NO FORCE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS candidate_skill_lookup_idx
  ON candidate_candidateskill (normalized_name, profile_id);
CREATE INDEX IF NOT EXISTS candidate_role_categories_gin
  ON candidate_candidateprofile USING gin (role_categories jsonb_path_ops);
CREATE INDEX IF NOT EXISTS candidate_locations_gin
  ON candidate_candidateprofile USING gin (preferred_locations jsonb_path_ops);
CREATE INDEX IF NOT EXISTS candidate_work_arrangements_gin
  ON candidate_candidateprofile USING gin (work_arrangements jsonb_path_ops);
ALTER TABLE candidate_candidateprofile FORCE ROW LEVEL SECURITY;
ALTER TABLE candidate_candidateskill FORCE ROW LEVEL SECURITY;
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


class Migration(migrations.Migration):
    dependencies = [("search", "0003_search_integrity")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
