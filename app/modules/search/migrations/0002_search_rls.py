from django.db import migrations


SQL = r"""
ALTER TABLE search_searchdefinition ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_searchdefinition FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON search_searchdefinition
USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE search_savedsearch ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_savedsearch FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON search_savedsearch
USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE search_criteriagroup ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_criteriagroup FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON search_criteriagroup USING (EXISTS (
 SELECT 1 FROM search_searchdefinition s WHERE s.id = search_id
 AND s.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid));

ALTER TABLE search_criterion ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_criterion FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON search_criterion USING (EXISTS (
 SELECT 1 FROM search_searchdefinition s WHERE s.id = search_id
 AND s.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid));

ALTER TABLE search_searchresultsnapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_searchresultsnapshot FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON search_searchresultsnapshot USING (EXISTS (
 SELECT 1 FROM search_searchdefinition s WHERE s.id = search_id
 AND s.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid));
"""

REVERSE = r"""
DROP POLICY IF EXISTS tenant_isolation ON search_searchresultsnapshot;
DROP POLICY IF EXISTS tenant_isolation ON search_criterion;
DROP POLICY IF EXISTS tenant_isolation ON search_criteriagroup;
DROP POLICY IF EXISTS tenant_isolation ON search_savedsearch;
DROP POLICY IF EXISTS tenant_isolation ON search_searchdefinition;
ALTER TABLE search_searchresultsnapshot DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_criterion DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_criteriagroup DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_savedsearch DISABLE ROW LEVEL SECURITY;
ALTER TABLE search_searchdefinition DISABLE ROW LEVEL SECURITY;
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE)


class Migration(migrations.Migration):
    dependencies = [("search", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
