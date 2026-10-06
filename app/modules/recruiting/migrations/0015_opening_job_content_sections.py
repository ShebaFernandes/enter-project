from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("recruiting", "0014_applicant_review_rls")]

    operations = [
        migrations.AddField(
            model_name="opening",
            name="company_name",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="opening",
            name="about_company",
            field=models.TextField(blank=True, max_length=10000),
        ),
        migrations.AddField(
            model_name="opening",
            name="role_summary",
            field=models.TextField(blank=True, max_length=10000),
        ),
        migrations.AddField(
            model_name="opening",
            name="responsibilities",
            field=models.TextField(blank=True, max_length=20000),
        ),
        migrations.AddField(
            model_name="opening",
            name="requirements",
            field=models.TextField(blank=True, max_length=20000),
        ),
        migrations.AddField(
            model_name="opening",
            name="nice_to_have",
            field=models.TextField(blank=True, max_length=10000),
        ),
        migrations.AddField(
            model_name="publicopeningprojection",
            name="company_name",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="publicopeningprojection",
            name="about_company",
            field=models.TextField(blank=True, max_length=10000),
        ),
        migrations.AddField(
            model_name="publicopeningprojection",
            name="role_summary",
            field=models.TextField(blank=True, max_length=10000),
        ),
        migrations.AddField(
            model_name="publicopeningprojection",
            name="responsibilities",
            field=models.TextField(blank=True, max_length=20000),
        ),
        migrations.AddField(
            model_name="publicopeningprojection",
            name="requirements",
            field=models.TextField(blank=True, max_length=20000),
        ),
        migrations.AddField(
            model_name="publicopeningprojection",
            name="nice_to_have",
            field=models.TextField(blank=True, max_length=10000),
        ),
    ]
