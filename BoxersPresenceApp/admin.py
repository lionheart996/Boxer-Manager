from django.contrib import admin
from .models import Boxer, Attendance, BatteryTest, TestResult, HeartRate

admin.site.register(Boxer)
admin.site.register(Attendance)

@admin.register(BatteryTest)
class BatteryTestAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "coach", "display_order", "created_at")
    list_filter  = ("coach",)
    search_fields = ("name", "coach__username")
    ordering = ("display_order", "name")

@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ("boxer", "test", "value1", "value2", "value3", "updated_at")
    list_filter  = ("test", "boxer")
    search_fields = ("boxer__name", "test__name")
    ordering = ("test__name", "boxer__name")

@admin.register(HeartRate)
class HeartRateAdmin(admin.ModelAdmin):
    list_display = ("boxer", "phase", "bpm", "measured_at", "updated_at")
    list_filter = ("phase", "measured_at")
    search_fields = ("boxer__name",)