from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0002_inventoryitem_skincareprofile_professional_notes_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="skincareprofile",
            name="questionnaire_responses",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="skincareprofile",
            name="last_questionnaire_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="skincareprofile",
            name="ai_morning_routine",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="skincareprofile",
            name="ai_evening_routine",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="skincareprofile",
            name="ai_recommended_products",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="skincareprofile",
            name="ai_recommendation_explanation",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="skincareprofile",
            name="ai_recommendation_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
