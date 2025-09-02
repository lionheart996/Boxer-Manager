# BoxersPresenceApp/admin.py
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Boxer,
    Attendance,
    BatteryTest,
    TestResult,
    HeartRate,
    CoachProfile,
    Gym, Weight, Enrollment, ClassTemplate,
)

# --- Simple registrations ---
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("boxer", "date")
    list_filter = ("date",)
    search_fields = ("boxer__name",)

# --- TestResult ---
class TestResultInline(admin.TabularInline):
    model = TestResult
    extra = 0
    fields = ("boxer", "measured_at", "value1", "value2", "value3", "notes")
    ordering = ("-measured_at",)

@admin.register(BatteryTest)
class BatteryTestAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "display_order")
    search_fields = ("name",)
    inlines = [TestResultInline]

@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ("boxer", "test", "measured_at", "value1", "value2", "value3")
    list_filter  = ("test", "boxer")
    search_fields = ("boxer__name", "test__name", "notes")
    ordering = ("-measured_at",)


# --- HeartRate ---
@admin.register(HeartRate)
class HeartRateAdmin(admin.ModelAdmin):
    list_display = ("boxer", "measured_at", "bpm", "notes")
    list_filter = ("boxer", "measured_at")
    ordering = ("-measured_at",)

# --- Boxer ---
@admin.register(Boxer)
class BoxerAdmin(admin.ModelAdmin):
    list_display = ("name", "parent_name", "date_of_birth", "gym")
    list_filter = ("gym",)
    search_fields = ("name", "parent_name")
    autocomplete_fields = ("gym",)
    filter_horizontal = ("coaches",)

# --- Gym ---
@admin.register(Gym)
class GymAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "location")
    search_fields = ("name", "location")


# --- CoachProfile standalone admin (optional but handy) ---
@admin.register(CoachProfile)
class CoachProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "gym")
    list_filter = ("gym",)
    search_fields = ("user__username", "user__email")


# --- Inline CoachProfile on the User page ---
class CoachProfileInline(admin.StackedInline):
    model = CoachProfile
    can_delete = False
    fk_name = "user"
    extra = 0           # ← important
    max_num = 1         # ← important


User = get_user_model()

# Unregister default user admin (if already registered), then re-register with inline
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = [CoachProfileInline]

@admin.register(Weight)
class WeightAdmin(admin.ModelAdmin):
    list_display = ("boxer", "kg", "measured_at")
    list_filter = ("boxer", "measured_at")
    search_fields = ("boxer__name",)

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    autocomplete_fields = ("boxer",)  # search box for selecting boxers
    verbose_name = "Enrolled boxer"
    verbose_name_plural = "Enrolled boxers"
    # If you want a remove (trash) icon, leave can_delete=True (default)

@admin.register(ClassTemplate)
class ClassTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "gym", "enrolled_count")
    list_filter  = ("gym",)
    search_fields = ("title",)
    fields = ("title", "gym", "coaches")  # drop "coaches" if you don't use it
    inlines = [EnrollmentInline]
    list_select_related = ("gym",)

    def enrolled_count(self, obj):
        return obj.enrollments.count()
    enrolled_count.short_description = "Boxers"
