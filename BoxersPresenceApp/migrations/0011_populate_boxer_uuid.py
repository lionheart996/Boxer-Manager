from django.db import migrations
import uuid

def populate_boxer_uuid(apps, schema_editor):
    Boxer = apps.get_model("BoxersPresenceApp", "Boxer")
    for boxer in Boxer.objects.filter(uuid__isnull=True):
        boxer.uuid = uuid.uuid4()
        boxer.save(update_fields=["uuid"])

class Migration(migrations.Migration):

    dependencies = [
        # set this to the migration you just created in Step 1
        ("BoxersPresenceApp", "0010_gym_remove_boxer_coach_boxer_date_of_birth_and_more"),
    ]

    operations = [
        migrations.RunPython(populate_boxer_uuid, migrations.RunPython.noop),
    ]

