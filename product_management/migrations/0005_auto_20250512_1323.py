from django.db import migrations
from django.utils import timezone

def convert_to_nested_format(apps, schema_editor):
    UserPreference = apps.get_model('product_management', 'UserPreference')
    for pref in UserPreference.objects.all():
        needs_update = False
        new_tags = {}
        for tag, value in pref.preferred_tags.items():
            if isinstance(value, dict):
                new_tags[tag] = value
            else:
                needs_update = True
                new_tags[tag] = {
                    'weight': float(value) if str(value).replace('.', '').isdigit() else 0,
                    'last_updated': timezone.now().isoformat()
                }
        if needs_update:
            pref.preferred_tags = new_tags
            pref.save()

class Migration(migrations.Migration):
    dependencies = [
        ('product_management', '0004_remove_userpreference_last_updated'),
    ]
    operations = [
        migrations.RunPython(convert_to_nested_format),
    ]