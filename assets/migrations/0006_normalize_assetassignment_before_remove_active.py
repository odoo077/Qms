from django.db import migrations
from django.utils import timezone


def normalize_asset_assignments(apps, schema_editor):
    """
    توحيد حالة العهد:
    - أي AssetAssignment غير نشط (active=False) وبدون date_to
      يُغلق تلقائيًا بوضع date_to = today
    الهدف: ضمان أن date_to هو المؤشر الوحيد للحالة.
    """
    AssetAssignment = apps.get_model("assets", "AssetAssignment")
    today = timezone.now().date()

    # أي سجل غير نشط لكنه ما زال مفتوحًا → نغلقه
    AssetAssignment.objects.filter(
        active=False,
        date_to__isnull=True,
    ).update(date_to=today)


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0005_remove_assetassignment_as_asg_one_open_per_asset_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_asset_assignments),
    ]
