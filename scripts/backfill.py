from datetime import datetime, time
from django.utils import timezone
from BoxersPresenceApp.models import Attendance, ClassSession, Enrollment

dummy_start = time(0, 0)
dummy_end   = time(1, 0)

for att in Attendance.objects.filter(session__isnull=True).select_related("boxer"):
    boxer = att.boxer
    enrollment = Enrollment.objects.filter(boxer=boxer).select_related("template").first()

    if not enrollment:
        print(f"⚠️ No enrollment found for {boxer.name}, skipping {att.date}")
        continue

    template = enrollment.template
    gym = boxer.gym

    start_dt = timezone.make_aware(datetime.combine(att.date, dummy_start))
    end_dt   = timezone.make_aware(datetime.combine(att.date, dummy_end))

    session, created = ClassSession.objects.get_or_create(
        gym=gym,
        template=template,
        start=start_dt,
        end=end_dt,
        defaults={"title": template.title},
    )

    att.session = session
    att.save()

    print(f"{'✅ Created' if created else 'ℹ️ Reused'} session '{template.title}' "
          f"for {att.date} | Linked {boxer.name}")
