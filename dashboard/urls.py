# dashboard/urls.py

from django.urls import path
from .views import (
    AdminDashboardView,
    SalesDashboardView,
    ChannelPartnerDashboardView,
)

urlpatterns = [
    path("admin/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("sales/", SalesDashboardView.as_view(), name="sales-dashboard"),
    path("channel-partner/", ChannelPartnerDashboardView.as_view(), name="cp-dashboard"),
]
