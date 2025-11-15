from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter

from . import views
from .api import BoxerViewSet, TestResultViewSet, TestViewSet, WeightViewSet
from .async_views import boxers_search
from .views import WeightProgressView, ParentHomeView, ParentAttendanceView, \
    ParentSignupView, GymCreateView, GymListView, BoxerTestsView, TestResultCreateView, BoxerClassesView, \
    BoxerCommentsView, EditCommentView, DeleteCommentView, export_attendance_preview, BoxerUpdateView, \
    SparringFinderView

router = DefaultRouter()
router.register(r'boxers', BoxerViewSet, basename='boxer')
router.register(r'tests', TestViewSet, basename='test')
router.register(r'results', TestResultViewSet, basename='testresult')
router.register(r'weights', WeightViewSet, basename='weight')



urlpatterns = [
    # Health / debug / export
    path("health/", views.health, name="health"),
    path("debug-urls/", views.debug_urls, name="debug-urls"),
    path("debug-env/", views.debug_env, name="debug-env"),
    path("export-fixture/", views.export_fixture, name="export-fixture"),

    # Boxers
    path('boxers/', views.BoxerListView.as_view(), name='boxer_list'),
    path("sparring-finder/", SparringFinderView.as_view(), name="sparring_finder"),
    path("boxers/<int:pk>/edit/", BoxerUpdateView.as_view(), name="boxer_edit"),
    path('boxers/delete/<int:pk>/', views.delete_boxer, name='delete_boxer'),
    path('boxer/<int:boxer_id>/report/', views.BoxerReportView.as_view(), name='boxer_report'),
    path('boxer/<int:boxer_id>/resume/', views.BoxerResumeView.as_view(), name='boxer_resume'),

    path("boxers/<int:boxer_id>/classes/", BoxerClassesView.as_view(), name="boxer_classes"),
    path("boxer/<uuid:uuid>/tests/", BoxerTestsView.as_view(), name="boxer_tests"),
    path("boxers/bulk-add/", views.BulkBoxerCreateView.as_view(), name="boxer_bulk_add"),
    path("boxers/<int:boxer_id>/comments/", BoxerCommentsView.as_view(), name="boxer_comments"),
    path("boxers/<int:boxer_id>/comments/<int:comment_id>/edit/", EditCommentView.as_view(), name="edit_comment"),
    path("boxers/<int:boxer_id>/comments/<int:comment_id>/delete/", DeleteCommentView.as_view(), name="delete_comment"),

    # Attendance
    path('attendance/', views.AttendanceListView.as_view(), name='attendance_list'),
    path("attendance/<int:pk>/edit/", views.attendance_edit, name="attendance_edit"),
    path("attendance/<int:pk>/delete/", views.attendance_delete, name="attendance_delete"),
    path('attendance/mark/', views.MarkAttendanceView.as_view(), name='mark_attendance'),
    path("export-attendance/", views.export_attendance_view, name="export_attendance"),
    path("export-attendance/excel/", views.export_attendance_excel, name="export_attendance_excel"),
    path("export-attendance/preview/", export_attendance_preview, name="export_attendance_preview"),
    path('attendance/weight/<int:boxer_id>/', WeightProgressView.as_view(), name='weight_progress'),
    path('attendance/date/', views.attendance_by_date, name='attendance_by_date'),
    path('attendance/delete/<int:attendance_id>/', views.delete_attendance, name='delete_attendance'),
    path('boxers/add/', views.add_boxer, name='add_boxer'),
    # Battery tests
    path('tests/', views.TestsListView.as_view(), name='tests_list'),
    path('tests/<int:pk>/edit/', views.TestUpdateView.as_view(), name='test_edit'),
    path('tests/<int:pk>/delete/', views.BatteryTestDeleteView.as_view(), name='battery_test_delete'),
    path(
        "tests/results/",
        RedirectView.as_view(pattern_name="tests_list", permanent=False),
        name="tests_results",
    ),
    path(
        "tests/summary/",
        RedirectView.as_view(pattern_name="tests_record", permanent=False),
        name="tests_summary",
    ),
    path('tests/rankings/', views.TestRankingView.as_view(), name='tests_rankings'),
    path('tests/rankings/<int:test_id>/', views.TestRankingView.as_view(), name='tests_rankings_for_test'),
    path("tests/record/", TestResultCreateView.as_view(), name="tests_record"),
    path("tests/record-multi/", views.TestResultBulkCreateView.as_view(), name="tests_record_multi"),

    path('heart-rate/record/', views.record_heart_rate, name='record_heart_rate'),
    path('heart-rate/summary/', views.HeartRateSummaryView.as_view(), name='heart_rate_summary'),
    path('heart-rate/boxer/<int:boxer_id>/', views.HeartRateDetailView.as_view(), name='heart_rate_detail'),
    path("heart-rate/boxer/<int:boxer_id>/add/", views.HeartRateCreateView.as_view(), name="heart_rate_add"),
    path('weight/record/', views.record_weight, name='record_weight'),
    path('weight/summary/', views.WeightSummaryView.as_view(), name='weight_summary'),
    path('weight/boxer/<int:boxer_id>/', views.WeightDetailView.as_view(), name='weight_detail'),


    # Async + API
    path('async/boxers-search/', boxers_search, name='boxers_search'),
    path('api/', include(router.urls)),
    path("api/class/attendance/", views.api_class_attendance, name="api_class_attendance"),
    path("api/calendar/enroll/", views.api_enroll, name="api_enroll"),
    path("api/calendar/attendance/", views.api_attendance_upsert, name="api_attendance_upsert"),
    path('parent/signup/', ParentSignupView.as_view(), name='parent_signup'),
    path('parent/', ParentHomeView.as_view(), name='parent_home'),
    path('parent/<int:boxer_id>/attendance/', ParentAttendanceView.as_view(), name='parent_attendance'),
    path('parent/<int:boxer_id>/weight/', WeightProgressView.as_view(), name='parent_weight'),
    path('attendance/weight/<int:boxer_id>/', WeightProgressView.as_view(), name='weight_progress'),
    path("calendar/", views.CalendarView.as_view(), name="calendar"),
    path("gyms/", GymListView.as_view(), name="gym_list"),
    path("gyms/add/", GymCreateView.as_view(), name="add_gym"),

]
