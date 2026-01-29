from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterUserView,MyTokenObtainPairView
from .views_assignable_users import AssignableUsersByAdminAPIView
from .views import (
    RegisterUserView,
UserViewSet,
    MyTokenObtainPairView,
    LoginOTPStartView,
    LoginOTPVerifyView,ProjectUserAccessUpsertAPIView
)
from .views import RegisterUserWithProjectAccessView

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")



urlpatterns = [
    path("register/", RegisterUserView.as_view(), name="register"),
    path("login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("login/otp/start/", LoginOTPStartView.as_view(), name="login_otp_start"),
    path("login/otp/verify/", LoginOTPVerifyView.as_view(), name="login_otp_verify"),
    path(
        "assignable-users/",
        AssignableUsersByAdminAPIView.as_view(),
        name="assignable-users-by-project",
    ),
    path("register-with-project/", RegisterUserWithProjectAccessView.as_view(), name="register-with-project"),
    path("project-user-access/",ProjectUserAccessUpsertAPIView.as_view(),name="project-user-access",),
    path("", include(router.urls)),

    
]
