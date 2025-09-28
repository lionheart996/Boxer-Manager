from typing import Any
from uuid import uuid4
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# ======================
# Gyms & Coaches
# ======================


class Gym(models.Model):
    name = models.CharField(max_length=120, unique=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return self.name

class CoachProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_profile")
    gym = models.ForeignKey(Gym, on_delete=models.SET_NULL, null=True, blank=True, related_name="coaches")

    def __str__(self):
        return f"{self.user.get_username()} ({self.gym.name if self.gym else 'No gym'})"

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_coach_profile(sender, instance, created, **kwargs):
    if created:
        gym, _ = Gym.objects.get_or_create(name="Default Gym")
        CoachProfile.objects.get_or_create(user=instance, defaults={"gym": gym})


# ======================
# Boxers
# ======================


class Boxer(models.Model):
    uuid = models.UUIDField(default=uuid4, editable=False, db_index=True)

    # keep this for now!
    name = models.CharField(max_length=120)

    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)

    date_of_birth = models.DateField(blank=True, null=True)
    parent_name = models.CharField(max_length=120, blank=True, default="")

    gym = models.ForeignKey("Gym", on_delete=models.PROTECT, related_name="boxers")
    coaches = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="coached_boxers")
    shared_with_gyms = models.ManyToManyField("Gym", blank=True, related_name="shared_boxers")

    parents = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="children",
        help_text="Parent accounts who can view this boxer’s attendance and weight"
    )

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.name


class BoxerComment(models.Model):
    boxer = models.ForeignKey("Boxer", on_delete=models.CASCADE, related_name="comments")
    coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="boxer_comments")
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.coach} on {self.boxer}"


# ======================
# Tests
# ======================


class BatteryTest(models.Model):
    name = models.CharField(max_length=255)
    display_order = models.IntegerField(default=0)
    unit = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="battery_tests"
    )

    def __str__(self):
        return self.name

class TestResult(models.Model):
    # Define constants
    PHASE_PRE = "prep"
    PHASE_BUILD = "build"
    PHASE_PEAK = "peak"
    PHASE_CHOICES = (
        (PHASE_PRE, "Preparation"),
        (PHASE_BUILD, "Build"),
        (PHASE_PEAK, "Peak"),
    )
    phase = models.CharField(max_length=16, choices=PHASE_CHOICES, db_index=True)

    boxer = models.ForeignKey(Boxer, on_delete=models.CASCADE, related_name="test_results")
    test = models.ForeignKey(BatteryTest, on_delete=models.CASCADE, related_name="results")

    measured_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recorded_results")

    value1 = models.FloatField(null=True, blank=True)
    value2 = models.FloatField(null=True, blank=True)
    value3 = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("boxer", "test", "phase", "measured_at")
        ordering = ["-measured_at"]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)  # <-- FIXED
        self.value = None

    def __str__(self) -> str:
        return f"{self.boxer.name} – {self.test.name} – {self.value}"


# ======================
# Parents
# ======================


class ParentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parent_profile")
    children = models.ManyToManyField(
        Boxer,
        blank=True,
        related_name="parent_profiles",  # ✅ unique reverse name on Boxer
        help_text="Boxers this parent/guardian can view"
    )

    def __str__(self):
        return f"Parent: {self.user.get_username()}"


# ======================
# Classes / Sessions
# ======================


class ClassTemplate(models.Model):

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"

    gym = models.ForeignKey(Gym, on_delete=models.PROTECT, related_name="class_templates")
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)  # <- add this
    coaches = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="class_templates", blank=True)

    def __str__(self):
        return f"{self.title} ({self.gym.name})"


# ======================
# Attendance & Vital signs
# ======================


class HeartRate(models.Model):
    boxer = models.ForeignKey("BoxersPresenceApp.Boxer", on_delete=models.CASCADE, related_name="heart_rates")
    measured_at = models.DateTimeField(db_index=True)
    bpm = models.PositiveIntegerField()
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-measured_at"]

    def __str__(self):
        return f"{self.boxer} — {self.bpm} bpm @ {self.measured_at:%Y-%m-%d %H:%M}"

class Weight(models.Model):
    boxer = models.ForeignKey("Boxer", on_delete=models.CASCADE, related_name="weights")
    measured_at = models.DateTimeField(default=timezone.now)
    kg = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ["-measured_at"]

    def __str__(self):
        return f"{self.boxer.name} – {self.kg} kg on {self.measured_at:%Y-%m-%d}"

class Attendance(models.Model):
    boxer = models.ForeignKey("Boxer", on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField(default=timezone.now)
    is_present = models.BooleanField(default=False)
    is_excused = models.BooleanField(default=False)

    class_template = models.ForeignKey(
        "ClassTemplate",
        on_delete=models.PROTECT,
        related_name="attendances",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("boxer", "date", "class_template")
        ordering = ["-date"]


class Enrollment(models.Model):
    boxer = models.ForeignKey(Boxer, on_delete=models.CASCADE, related_name="enrollments")
    template = models.ForeignKey(ClassTemplate, on_delete=models.CASCADE, related_name="enrollments")

    class Meta:
        unique_together = ("boxer", "template")
