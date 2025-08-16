from django.urls import path
from . import views

urlpatterns = [
    # Boxers
    path('boxers/', views.BoxerListView.as_view(), name='boxer_list'),
    path('boxers/delete/<int:pk>/', views.delete_boxer, name='delete_boxer'),
    path('boxer/<int:boxer_id>/report/', views.BoxerReportView.as_view(), name='boxer_report'),
    path('boxer/<int:boxer_id>/tests/', views.BoxerTestsView.as_view(), name='boxer_tests'),

    # Attendance
    path('attendance/', views.AttendanceListView.as_view(), name='attendance_list'),
    path('attendance/mark/', views.MarkAttendanceView.as_view(), name='mark_attendance'),
    path('attendance/date/', views.attendance_by_date, name='attendance_by_date'),
    path('attendance/delete/<int:attendance_id>/', views.delete_attendance, name='delete_attendance'),

    # Battery tests
    path('tests/', views.TestsListView.as_view(), name='tests_list'),
    path('tests/<int:pk>/edit/', views.TestUpdateView.as_view(), name='test_edit'),
    path('tests/<int:pk>/delete/', views.TestDeleteView.as_view(), name='test_delete'),
    path('tests/results/', views.ResultsMatrixView.as_view(), name='tests_results'),
    path('tests/results/save/', views.ResultsCellSaveView.as_view(), name='tests_result_save'),
    path('tests/summary/', views.BoxerResultsSummaryView.as_view(), name='tests_summary'),
    path('tests/manage-boxers/', views.BoxerPerformanceView.as_view(), name='tests_manage_boxers'),
    path('boxers/add/', views.add_boxer, name='add_boxer'),
    path('tests/summary/save/', views.summary_result_save, name='tests_summary_save'),
    path('tests/summary/delete/', views.summary_result_delete, name='tests_summary_delete'),
    path('tests/result/edit/', views.TestResultEditView.as_view(), name='tests_result_edit'),
    path('heart-rate/record/', views.record_heart_rate, name='record_heart_rate'),
    path('heart-rate/summary/', views.HeartRateSummaryView.as_view(), name='heart_rate_summary'),
    path('heart-rate/boxer/<int:boxer_id>/', views.HeartRateDetailView.as_view(), name='heart_rate_detail'),
    path('weight/record/', views.record_weight, name='record_weight'),
    path('weight/summary/', views.WeightSummaryView.as_view(), name='weight_summary'),
    path('weight/boxer/<int:boxer_id>/', views.WeightDetailView.as_view(), name='weight_detail'),
    path('tests/rankings/', views.TestRankingView.as_view(), name='tests_rankings'),
    path('tests/rankings/<int:test_id>/', views.TestRankingView.as_view(), name='tests_rankings_for_test'),
]

