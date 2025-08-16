from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class Boxer(models.Model):
    coach = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Attendance(models.Model):
    boxer = models.ForeignKey(Boxer, on_delete=models.CASCADE)
    date = models.DateField()
    is_present = models.BooleanField(default=False)
    is_excused = models.BooleanField(default=False)

    def __str__(self):
        status = 'Present' if self.is_present else 'Absent (Excused)' if self.is_excused else 'Absent'
        return f"{self.boxer.name} - {self.date} - {status}"

class BatteryTest(models.Model):
    coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='battery_tests')
    name = models.CharField(max_length=120)
    unit = models.CharField(max_length=32)  # REQUIRED (we already enforce)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = ("coach", "name")

    @property
    def display_label(self):
        return f"{self.name} [{self.unit}]" if self.unit else self.name

    def __str__(self): return self.display_label


class TestResult(models.Model):
    PHASE_PRE = "pre"
    PHASE_MID = "mid"
    PHASE_BEFORE = "before"
    PHASE_CHOICES = [
        (PHASE_PRE, "Pre season"),
        (PHASE_MID, "Mid season"),
        (PHASE_BEFORE, "Before Tournament"),
    ]

    boxer = models.ForeignKey("Boxer", on_delete=models.CASCADE, related_name="test_results")
    test = models.ForeignKey(BatteryTest, on_delete=models.CASCADE, related_name="results")
    phase = models.CharField(max_length=10, choices=PHASE_CHOICES, default=PHASE_PRE)

    value1 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    value2 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    value3 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    notes = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("boxer", "test", "phase")  # ← separate row per phase

    def __str__(self): return f"{self.boxer} – {self.test.display_label} – {self.get_phase_display()}"

class HeartRate(models.Model):
    boxer = models.ForeignKey(Boxer, on_delete=models.CASCADE, related_name="heart_rates")
    phase = models.CharField(max_length=10, choices=TestResult.PHASE_CHOICES)
    bpm = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(30), MaxValueValidator(240)]
    )
    measured_at = models.DateField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("boxer", "phase")
        ordering = ["-measured_at", "-updated_at"]

    def __str__(self):
        return f"{self.boxer.name} – {self.get_phase_display()} – {self.bpm} bpm"

class Weight(models.Model):
    boxer = models.ForeignKey(Boxer, on_delete=models.CASCADE, related_name="weights")
    phase = models.CharField(max_length=10, choices=TestResult.PHASE_CHOICES)
    kg = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0)])
    expected_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    measured_at = models.DateField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("boxer", "phase")  # one record per boxer+phase
        ordering = ["-measured_at", "-updated_at"]

    def __str__(self):
        return f"{self.boxer.name} — {self.get_phase_display()} — {self.kg} kg"