# -*- coding: utf-8 -*-
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "boxers_project.settings")
django.setup()

from BoxersPresenceApp.models import Attendance

updated = Attendance.objects.update(session=None)
print(f"🔄 Reset {updated} attendances (session cleared)")

