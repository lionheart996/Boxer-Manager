from django.db import migrations

def copy_session_to_class_template(apps, schema_editor):
    Attendance = apps.get_model("BoxersPresenceApp", "Attendance")
    for att in Attendance.objects.all():
        # only if you still have session column in DB backup
        if hasattr(att, "session") and att.session_id and att.session and att.session.template_id:
            att.class_template_id = att.session.template_id
            att.save(update_fields=["class_template"])

class Migration(migrations.Migration):
    dependencies = [
        ("BoxersPresenceApp", "0030_alter_attendance_unique_together"),
    ]

    operations = [
        migrations.RunPython(copy_session_to_class_template, migrations.RunPython.noop),
    ]
