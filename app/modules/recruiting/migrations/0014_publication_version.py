from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("recruiting", "0013_public_opening_projection")]
    operations = [
        migrations.AddField(
            model_name="publicopeningprojection",
            name="version",
            field=models.PositiveBigIntegerField(default=1),
        ),
    ]
