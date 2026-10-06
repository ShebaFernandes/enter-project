from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("candidate", "0006_reconcile_finding_discovery_policy")]

    operations = [
        migrations.AddField(
            model_name="candidateprofile",
            name="education",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
