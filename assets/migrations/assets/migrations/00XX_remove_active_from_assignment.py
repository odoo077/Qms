from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("assets", "00XX_previous_migration"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="assetassignment",
            name="active",
        ),
    ]
