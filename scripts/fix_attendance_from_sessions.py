from BoxersPresenceApp.models import Attendance, SessionAttendance
from django.utils import timezone

count = 0

for sa in SessionAttendance.objects.select_related("session__template", "boxer"):
    att, created = Attendance.objects.get_or_create(
        boxer=sa.boxer,
        date=sa.session.start.date(),
        defaults={
            "is_present": sa.present,
            "is_excused": sa.excused,
            "session": sa.session,
        }
    )

    # Update if already exists
    att.is_present = sa.present
    att.is_excused = sa.excused
    att.session = sa.session
    att.save()

    count += 1

print(f"✅ Synced {count} attendance records from SessionAttendance")
