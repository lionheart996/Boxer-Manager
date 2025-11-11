# BoxersPresenceApp/admin.py
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import OuterRef, Subquery

from .models import (
    Boxer,
    Attendance,
    BatteryTest,
    TestResult,
    HeartRate,
    CoachProfile,
    Gym, Weight, Enrollment, ClassTemplate, ParentProfile,
)
from .utils import calc_age, age_band, olympic_weight_class


# --- Simple registrations ---
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("date", "class_name", "boxer", "status")
    list_filter = ("date", "class_template", "is_present", "is_excused")
    search_fields = ("boxer__name", "class_template__title", "class_template__gym__name")

    def class_name(self, obj):
        return obj.class_template.title if obj.class_template else "-"
    class_name.short_description = "Class"

    def status(self, obj):
        if obj.is_present:
            return "Present"
        return "Excused" if obj.is_excused else "Absent"
    status.short_description = "Attendance Status"

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

@admin.register(Boxer)
class BoxerAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "gender",
        "display_age",
        "age_band_display",
        "latest_weight_display",
        "weight_class_display",
        "gym",
    )
    list_filter = ("gym", "gender")
    search_fields = ("first_name", "last_name", "parent_name")
    autocomplete_fields = ("gym",)
    filter_horizontal = ("coaches",)
    readonly_fields = ("uuid",)
    ordering = ("last_name", "first_name")

    fieldsets = (
        ("Identity", {
            "fields": ("uuid", "first_name", "last_name", "name", "gender", "date_of_birth", "parent_name"),
        }),
        ("Affiliations", {
            "fields": ("gym", "coaches", "shared_with_gyms", "parents"),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        latest_weight_qs = Weight.objects.filter(boxer=OuterRef("pk")).order_by("-measured_at")
        return qs.annotate(
            latest_kg=Subquery(latest_weight_qs.values("kg")[:1]),
            latest_measured_at=Subquery(latest_weight_qs.values("measured_at")[:1]),
        )

    # --- Computed columns ---
    def display_age(self, obj):
        age = calc_age(obj.date_of_birth)
        return age if age is not None else "—"
    display_age.short_description = "Age"

    def age_band_display(self, obj):
        a = calc_age(obj.date_of_birth)
        return age_band(a) or "—"
    age_band_display.short_description = "Band"

    def latest_weight_display(self, obj):
        return f"{obj.latest_kg:.1f} kg" if obj.latest_kg else "—"
    latest_weight_display.short_description = "Latest weight"

    def weight_class_display(self, obj):
        age = calc_age(obj.date_of_birth)
        wc = olympic_weight_class(obj.latest_kg, obj.gender, age)
        return wc or "—"
    weight_class_display.short_description = "Weight class"

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

@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "children_list")
    search_fields = ("user__username", "user__email")

    def children_list(self, obj):
        return ", ".join(b.name for b in obj.children.all())
    children_list.short_description = "Children"

from django.contrib import admin
from .models import BoxerComment


@admin.register(BoxerComment)
class BoxerCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "boxer", "coach", "short_text", "created_at")
    list_filter = ("created_at", "coach", "boxer")
    search_fields = ("text", "coach__username", "coach__first_name", "coach__last_name", "boxer__first_name", "boxer__last_name")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def short_text(self, obj):
        return (obj.text[:50] + "...") if len(obj.text) > 50 else obj.text
    short_text.short_description = "Comment"