from django.db import migrations

SEED_CATEGORIES = [
    "Cafe",
    "Coffee shop",
    "Bar",
    "Restaurant",
    "Park",
    "Museum",
    "Gallery",
    "Historical place",
    "Nature",
    "Entertainment",
    "Shopping",
    "Other",
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("categories", "Category")
    for name in SEED_CATEGORIES:
        if not Category.objects.filter(name__iexact=name).exists():
            Category.objects.create(name=name)


def unseed_categories(apps, schema_editor):
    Category = apps.get_model("categories", "Category")
    Category.objects.filter(name__in=SEED_CATEGORIES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("categories", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
