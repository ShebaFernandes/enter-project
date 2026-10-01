from django.db import migrations


SQL = r"""
ALTER TABLE tenancy_accessreview ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_accessreview FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenancy_accessreview
USING (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid)
WITH CHECK (tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tenancy_accessreviewitem ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_accessreviewitem FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenancy_accessreviewitem
USING (EXISTS (
    SELECT 1 FROM tenancy_accessreview review
    WHERE review.id = review_id
      AND review.tenant_id = nullif(current_setting('app.tenant_id', true), '')::uuid
));
"""

REVERSE = r"""
DROP POLICY IF EXISTS tenant_isolation ON tenancy_accessreviewitem;
DROP POLICY IF EXISTS tenant_isolation ON tenancy_accessreview;
ALTER TABLE tenancy_accessreviewitem DISABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_accessreview DISABLE ROW LEVEL SECURITY;
"""


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE)


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0006_accessreview_accessreviewitem_and_more")]
    operations = [migrations.RunPython(forwards, backwards)]
