from django.urls import path

from .views import AuditLogListView, DashboardSummaryView

urlpatterns = [
    path("audit/", AuditLogListView.as_view(), name="audit-list"),
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
]
