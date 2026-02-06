from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from .serializers import RegisterUserSerializer, UserSerializer
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from .serializers import MyTokenObtainPairSerializer   
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (
    RegisterUserSerializer,
    UserSerializer,
    MyTokenObtainPairSerializer,
    LoginOTPStartSerializer,
    LoginOTPVerifySerializer,
    UserSerializer,
)
from .models import LoginOTP
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from .utils import (
    build_brand_payload_for_user,
    build_authorized_projects_payload,
)

User = get_user_model()
from django.conf import settings
from .models import ClientBrand, Role  # adjust import paths
from django.db.models import Q 


class UserViewSet(viewsets.ModelViewSet):
    """
    /api/accounts/users/        [ADMIN/SUPERADMIN only – list, create, etc.]
    /api/accounts/users/<id>/   [ADMIN or self – retrieve/update]
    /api/accounts/users/me/     [GET, PATCH] current user's profile + signature
    """
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # 👈 so signature file upload works
    def get_queryset(self):
        user = self.request.user

        # Staff / Superuser => all
        if user.is_superuser or user.is_staff or getattr(user, "role", None) == Role.SUPERADMIN:
            return User.objects.all().order_by("id")

        role = getattr(user, "role", None)

        # ADMIN => only admin + his team members
        if role == Role.ADMIN:
            return User.objects.filter(Q(id=user.id) | Q(admin_id=user.id)).order_by("id")

        # Team users => only their admin bucket (admin + all team)
        admin_id = getattr(user, "admin_id", None)
        if admin_id:
            return User.objects.filter(Q(id=admin_id) | Q(admin_id=admin_id)).order_by("id")

        # fallback => only self
        return User.objects.filter(id=user.id)
    def perform_create(self, serializer):
        creator = self.request.user if self.request.user.is_authenticated else None

        # If ADMIN creates a user, auto-bind new user under that admin tenant
        if creator and getattr(creator, "role", None) == Role.ADMIN:
            serializer.save(created_by=creator, admin=creator)
            return

        serializer.save(created_by=creator)


    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """
        GET  /api/accounts/users/me/      -> current user profile (incl. signature)
        PATCH /api/accounts/users/me/    -> update profile + signature
        """
        user = request.user

        if request.method == "GET":
            ser = self.get_serializer(user)
            return Response(ser.data)

        # PATCH (partial update)
        ser = self.get_serializer(user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_200_OK)



class RegisterUserView(APIView):
    """
    POST /api/accounts/register/
      body: { username, password, first_name?, last_name?, email?, role, admin_id? }
    Auth required; permissions enforced in serializer.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = RegisterUserSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)



class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer




# ------------- NEW: OTP LOGIN VIEWS -----------------

class LoginOTPStartView(APIView):
    """
    POST /api/accounts/login/otp/start/
    { "email": "user@example.com" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        ser = LoginOTPStartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower()

        try:
            user = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"detail": "No active user found with this email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create OTP (and invalidate old ones if you want)
        otp_obj = LoginOTP.create_otp_for_email(email)

        # Send email (replace with your own mail util if you have one)
        subject = "Your login OTP"
        message = f"Your OTP for login is {otp_obj.code}. It is valid for 5 minutes."
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

        try:
            send_mail(subject, message, from_email, [email], fail_silently=False)
        except Exception as e:
            # Optional: delete OTP if email fails
            otp_obj.delete()
            return Response(
                {"detail": "Unable to send OTP email right now."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"detail": "OTP sent to your email."},
            status=status.HTTP_200_OK,
        )


class LoginOTPVerifyView(APIView):
    """
    POST /api/accounts/login/otp/verify/
    Body:
      { "email": "user@example.com", "otp": "123456" }

    Response:
      { "refresh": "...", "access": "...", "user": { ... }, "brand": {...}, "projects": [...] }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # 1) Validate input
        serializer = LoginOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        code = serializer.validated_data["otp"]

        # 2) Resolve user (case-insensitive, handle duplicates safely)
        qs = (
            User.objects
            .filter(email__iexact=email, is_active=True)
            .order_by("id")
        )

        if not qs.exists():
            return Response(
                {"detail": "Invalid email or OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Even if by mistake 2 users hain, first pick karenge
        user = qs.first()

        # 3) Latest valid, unused OTP for this email
        otp_obj = (
            LoginOTP.objects
            .filter(email__iexact=email, is_used=False)
            .order_by("-created_at")
            .first()
        )

        if not otp_obj:
            return Response(
                {"detail": "OTP expired or not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        if now > otp_obj.valid_until:
            otp_obj.is_used = True
            otp_obj.save(update_fields=["is_used"])
            return Response(
                {"detail": "OTP has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_obj.code != code:
            return Response(
                {"detail": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4) Mark OTP as used
        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])

        # 5) Issue JWT tokens (same payload as normal login)
        refresh = MyTokenObtainPairSerializer.get_token(user)
        access = refresh.access_token

        signature_url = None
        if getattr(user, "signature", None):
            try:
                signature_url = request.build_absolute_uri(user.signature.url)
            except Exception:
                signature_url = user.signature.url  # fallback

        user_payload = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "signature": signature_url,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "admin_id": user.admin_id,
        }

        # 🔹 Brand
        brand_payload = build_brand_payload_for_user(user, request=request)

        # 🔹 Authorised projects
        projects_payload = build_authorized_projects_payload(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(access),
                "user": user_payload,
                "brand": brand_payload,
                "projects": projects_payload,
            },
            status=status.HTTP_200_OK,
        )




from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .serializers import RegisterUserWithProjectsSerializer
from .serializers import UserSerializer  # <- adjust to your actual UserSerializer import
from .models import ProjectUserAccess  # adjust path
from .serializers_project_access import ProjectUserAccessSerializer  # optional (below)


class RegisterUserWithProjectAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = RegisterUserWithProjectsSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = ser.save()

        accesses = ProjectUserAccess.objects.filter(user=user).select_related("project").order_by("id")

        return Response(
            {
                "user": UserSerializer(user, context={"request": request}).data,
                "project_accesses": ProjectUserAccessSerializer(accesses, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


# accounts/views.py (BOTTOM में add करो)

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import ProjectUserAccess


class ProjectUserAccessUpsertAPIView(APIView):
    """
    POST /api/accounts/project-user-access/

    Body:
    {
      "user": 10,
      "project_ids": [1,2],
      "manager": 5,
      "can_view": true,
      "can_edit": false
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("user")
        project_ids = request.data.get("project_ids", [])
        manager_id = request.data.get("manager")
        can_view = request.data.get("can_view", True)
        can_edit = request.data.get("can_edit", False)

        if not user_id or not project_ids:
            return Response(
                {"detail": "user and project_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # delete old mappings
        ProjectUserAccess.objects.filter(user_id=user_id).delete()

        # create new mappings
        objs = []
        for pid in project_ids:
            objs.append(
                ProjectUserAccess(
                    user_id=user_id,
                    project_id=pid,
                    manager_id=manager_id,
                    can_view=can_view,
                    can_edit=can_edit,
                    is_active=True,
                )
            )

        ProjectUserAccess.objects.bulk_create(objs)

        return Response(
            {"detail": "Project user access updated successfully"},
            status=status.HTTP_200_OK,
        )
