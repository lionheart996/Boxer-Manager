from django.db import migrations, models
import uuid


def backfill_boxer_uuid(apps, schema_editor):
    Boxer = apps.get_model("BoxersPresenceApp", "Boxer")
    # Ensure every row has a unique uuid BEFORE we add the unique constraint
    seen = set()
    # Iterate deterministically to reduce duplicate generation
    for boxer in Boxer.objects.all().only("id", "uuid").order_by("id"):
        val = getattr(boxer, "uuid", None)
        needs_new = (val is None) or (str(val) == "") or (val in seen)
        if not needs_new:
            # Also check DB-level duplicates just in case
            if Boxer.objects.filter(uuid=val).exclude(id=boxer.id).exists():
                needs_new = True
        if needs_new:
            new_val = uuid.uuid4()
            # Avoid rare collisions
            while (new_val in seen) or Boxer.objects.filter(uuid=new_val).exists():
                new_val = uuid.uuid4()
            boxer.uuid = new_val
            boxer.save(update_fields=["uuid"])
            val = new_val
        seen.add(val)


class Migration(migrations.Migration):

    dependencies = [
        ("BoxersPresenceApp", "0011_populate_boxer_uuid")  # If this file doesn't exist, change to the last applied migration
        # If you didn't create 0011, set this to your previous migration (run `python manage.py showmigrations BoxersPresenceApp`)
    ]

    operations = [
        migrations.RunPython(backfill_boxer_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="boxer",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]

