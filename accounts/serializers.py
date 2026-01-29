from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Role,User,ClientBrand

User = get_user_model()



class ClientBrandSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = ClientBrand
        fields = ["company_name", "logo_url", "primary_color", "secondary_color"]

    def get_logo_url(self, obj):
        request = self.context.get("request")
        if obj.logo and hasattr(obj.logo, "url"):
            return request.build_absolute_uri(obj.logo.url)
        return None


class UserSerializer(serializers.ModelSerializer):
    signature = serializers.ImageField(required=False, allow_null=True)
    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "admin", "created_by", "is_active", "date_joined",       "signature"
        ]
        read_only_fields = ["id", "created_by", "date_joined"]


class RegisterUserSerializer(serializers.ModelSerializer):
    """
    Rules:
      - Only is_staff can create role=ADMIN.
      - Only is_staff OR role=ADMIN can create RECEPTION/SALES.
      - For RECEPTION/SALES:
          - If requester is ADMIN and admin is omitted, default admin=request.user.
          - If requester is is_staff, admin must be provided.
      - created_by is always set to request.user.
    """
    password = serializers.CharField(write_only=True, min_length=6, required=True)
    admin_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = [
            "username", "password",
            "first_name", "last_name", "email",
            "role", "admin_id"
        ]

    def validate(self, data):
        request = self.context["request"]
        creator: User = request.user
        role = data.get("role") or Role.SALES
        admin_id = data.get("admin_id")

        # Creating ADMINs:
        if role == Role.ADMIN:
            if not creator.is_staff:
                raise serializers.ValidationError("Only staff can create ADMIN users.")
            if admin_id:
                raise serializers.ValidationError("ADMIN users cannot have an admin owner.")

        if role in (Role.RECEPTION, Role.SALES):
            if not (creator.is_staff or getattr(creator, "role", None) == Role.ADMIN):
                raise serializers.ValidationError("Only staff or admins can create non-admin roles.")
            if creator.is_staff:
                if not admin_id:
                    raise serializers.ValidationError("admin_id is required when staff creates non-admin users.")
            else:
                if not admin_id:
                    data["admin_id"] = creator.id

        return data

    def create(self, validated_data):
        request = self.context["request"]
        creator: User = request.user

        admin_id = validated_data.pop("admin_id", None)
        role = validated_data.get("role") or Role.SALES
        raw_password = validated_data.pop("password")

        user = User(**validated_data)

        if role in (Role.RECEPTION, Role.SALES):
            if admin_id:
                try:
                    admin_user = User.objects.get(id=admin_id, role=Role.ADMIN)
                except User.DoesNotExist:
                    raise serializers.ValidationError("admin_id must point to a valid ADMIN user.")
                user.admin = admin_user
            else:
                user.admin_id = user.admin_id or getattr(creator, "id", None)

        user.created_by = creator

        user.set_password(raw_password)
        user.full_clean()  
        user.save()
        return user


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .utils import (
    build_brand_payload_for_user,
    build_authorized_projects_payload,
)






class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # 🔹 Extra claims inside JWT
        token["username"] = user.username
        token["role"] = user.role
        token["is_staff"] = user.is_staff
        token["is_superuser"] = user.is_superuser
        if user.admin_id:
            token["admin_id"] = user.admin_id

        return token

    def validate(self, attrs):
        """
        This defines WHAT the /login response looks like.
        """
        data = super().validate(attrs)
        user = self.user

        # 🔹 User payload
        data["user"] = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "admin_id": user.admin_id,
        }

        # 🔹 Brand payload (for theme)
        request = self.context.get("request")
        brand_payload = build_brand_payload_for_user(user, request=request)
        data["brand"] = brand_payload  # can be None if no brand configured

        # 🔹 Authorised projects payload
        data["projects"] = build_authorized_projects_payload(user)

        return data





class LoginOTPStartSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LoginOTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)






from django.db import transaction
from rest_framework import serializers

from .models import User, Role
from clientsetup.models import Project
from .models import ProjectUserAccess  # <- adjust import if file name differs


NON_ADMIN_ROLES = (
    Role.RECEPTION,
    Role.SALES,
    Role.CP,
    Role.CALLING_TEAM,
    Role.KYC,
    Role.FULL_CONTROL,
    Role.MANAGER,
)


class RegisterUserWithProjectsSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6, required=True)

    admin_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    # ✅ New: multiple projects
    project_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=False,
    )

    # ✅ Backward compatible: single project
    project_id = serializers.IntegerField(write_only=True, required=False)

    can_view = serializers.BooleanField(write_only=True, required=False, default=True)
    can_edit = serializers.BooleanField(write_only=True, required=False, default=True)

    class Meta:
        model = User
        fields = [
            "username", "password",
            "first_name", "last_name", "email",
            "role", "admin_id",
            "project_id", "project_ids",
            "can_view", "can_edit",
        ]

    def validate(self, data):
        request = self.context["request"]
        creator: User = request.user

        role = data.get("role") or Role.SALES
        data["role"] = role

        admin_id = data.get("admin_id")

        # ✅ normalize projects: allow either project_id or project_ids
        pids = data.get("project_ids")
        pid_single = data.get("project_id")

        if not pids and not pid_single:
            raise serializers.ValidationError(
                {"project_ids": "Send project_ids (list) or project_id (single)."}
            )

        if not pids and pid_single:
            pids = [pid_single]

        # de-dupe
        pids = list(dict.fromkeys(pids))

        # validate all projects exist
        existing = set(Project.objects.filter(id__in=pids).values_list("id", flat=True))
        missing = [x for x in pids if x not in existing]
        if missing:
            raise serializers.ValidationError({"project_ids": f"Invalid project ids: {missing}"})

        # Creating ADMIN
        if role == Role.ADMIN:
            if not creator.is_staff:
                raise serializers.ValidationError("Only staff can create ADMIN users.")
            if admin_id:
                raise serializers.ValidationError("ADMIN users cannot have an admin owner.")

        # Creating non-admin roles
        if role in NON_ADMIN_ROLES:
            if not (creator.is_staff or getattr(creator, "role", None) == Role.ADMIN):
                raise serializers.ValidationError(
                    "Only staff or ADMIN users can create non-admin roles."
                )

            if creator.is_staff:
                if not admin_id:
                    raise serializers.ValidationError(
                        {"admin_id": "admin_id is required when staff creates non-admin users."}
                    )
            else:
                if not admin_id:
                    data["admin_id"] = creator.id

        # store normalized list back
        data["project_ids"] = pids
        data.pop("project_id", None)
        return data

    def create(self, validated_data):
        request = self.context["request"]
        creator: User = request.user

        raw_password = validated_data.pop("password")
        admin_id = validated_data.pop("admin_id", None)

        project_ids = validated_data.pop("project_ids")
        can_view = validated_data.pop("can_view", True)
        can_edit = validated_data.pop("can_edit", True)

        role = validated_data.get("role") or Role.SALES

        with transaction.atomic():
            user = User(**validated_data)

            if role in NON_ADMIN_ROLES:
                if admin_id:
                    try:
                        admin_user = User.objects.get(id=admin_id, role=Role.ADMIN)
                    except User.DoesNotExist:
                        raise serializers.ValidationError(
                            {"admin_id": "admin_id must point to a valid ADMIN user."}
                        )
                    user.admin = admin_user
                else:
                    user.admin_id = user.admin_id or getattr(creator, "id", None)

            user.created_by = creator
            user.set_password(raw_password)
            user.full_clean()
            user.save()

            projects = Project.objects.filter(id__in=project_ids)

            access_rows = [
                ProjectUserAccess(
                    user=user,
                    project=p,
                    can_view=can_view,
                    can_edit=can_edit,
                    is_active=True,
                )
                for p in projects
            ]
            ProjectUserAccess.objects.bulk_create(access_rows)

        return user
