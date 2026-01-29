# booking/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_kyc import (
    BookingKycRequestCreateAPIView,
    BookingKycRequestDetailAPIView,
    BookingKycOneTimeDetailAPIView,
    BookingKycDecisionAPIView,
    BookingKycRequestListForKycAPIView,
BookingKycRequestApproveAPIView,
    BookingKycLinkToBookingAPIView,
)
from .views import BookingViewSet

router = DefaultRouter()
router.register(r"bookings", BookingViewSet, basename="booking")

urlpatterns = [
    path("", include(router.urls)),

    path("kyc-requests/", BookingKycRequestCreateAPIView.as_view(),
         name="booking-kyc-create"),

    path("kyc-requests/<int:pk>/decision/",
         BookingKycDecisionAPIView.as_view(),
         name="booking-kyc-decision"),

    path("kyc-requests/<int:pk>/",
         BookingKycRequestDetailAPIView.as_view(),
         name="booking-kyc-detail"),

    path("kyc-requests/one-time/<str:token>/",
         BookingKycOneTimeDetailAPIView.as_view(),
         name="booking-kyc-one-time-detail"),

    path("kyc-requests/kyc-team/", BookingKycRequestListForKycAPIView.as_view(), name="kyc-request-list-kyc-team"),

    path("bookings/<int:booking_id>/link-kyc-request/", BookingKycLinkToBookingAPIView.as_view(), name="booking-link-kyc"),

path("kyc-requests/<int:pk>/approve/",BookingKycRequestApproveAPIView.as_view(),name="booking-kyc-approve",),

]
