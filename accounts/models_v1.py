# accounts/models.py
from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.core.exceptions import ValidationError
from django.db import models
import string
import random

from django.utils import timezone
from datetime import timedelta


class Role(models.TextChoices):
    SUPERADMIN    = "SUPER_ADMIN", "Super Admin"
    ADMIN         = "ADMIN", "Admin"
    FULL_CONTROL  = "FULL_CONTROL", "Full Control"
    MANAGER       = "MANAGER", "Manager"
    RECEPTION     = "RECEPTION", "Reception"
    CP            = "CHANNEL_PARTNER", "Channel Partner"
    SALES         = "SALES", "SalesPerson"
    CALLING_TEAM  = "CALLING_TEAM", "Calling Team"
    KYC           = "KYC_TEAM", "KYC Team"

class UserManager(DjangoUserManager):
    """
    Django 5.x ke liye custom manager:
    make_random_password khud implement kar rahe hain.
    """
    def make_random_password(self, length=10, allowed_chars=None):
        if allowed_chars is None:
            allowed_chars = string.ascii_letters + string.digits
        return ''.join(random.choice(allowed_chars) for _ in range(length))


class User(AbstractUser):
    """
    - role: business role (ADMIN / RECEPTION / SALES / CHANNEL_PARTNER)
    - admin: for RECEPTION/SALES/CP, the owning admin (FK to a User with role=ADMIN)
    - created_by: who created this user (staff or admin)
    """

    # 🔹 Email now unique + required
    email = models.EmailField(
        unique=True,
        blank=False,
        null=False,
        error_messages={"unique": "A user with that email already exists."},
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        null=True,
        blank=True,
        default=Role.SALES,
        help_text="Business role",
    )

    admin = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="team_members",
        limit_choices_to={"role": Role.ADMIN},
        help_text="Owning admin for RECEPTION/SALES/CP",
    )

    created_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_users",
        help_text="Who created this user",
    )
    signature = models.ImageField(
        upload_to="user_signatures/",
        null=True,
        blank=True,
        help_text="Scanned/drawn signature image (PNG/JPEG).",
    )

    objects = UserManager()

    def clean(self):
        if self.role == Role.ADMIN and self.admin_id:
            raise ValidationError("Admin users cannot reference another admin.")

        if self.role in (Role.RECEPTION, Role.SALES, Role.CP, Role.CALLING_TEAM, Role.KYC) and not self.admin_id:
            raise ValidationError("Non-admin roles must reference an admin.")


# accounts/models.py (or wherever ClientBrand lives)
from django.db import models
from django.conf import settings


class ClientBrand(models.Model):
    admin = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_brand",
        limit_choices_to={"role": Role.ADMIN},
    )

    company_name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to="client_logos/", blank=True, null=True)

    # Colors
    primary_color = models.CharField(
        max_length=7,
        default="#102A54",  # your base color
        help_text="Primary brand color (navbar/footer, primary surfaces).",
    )
    secondary_color = models.CharField(
        max_length=7,
        default="#FFFFFF",
        help_text="Secondary brand color (e.g. text on primary surfaces).",
    )
    background_color = models.CharField(
        max_length=7,
        default="#F5F5F7",
        help_text="Default page background color.",
    )

    # Typography
    font_family = models.CharField(
        max_length=100,
        default="Inter",
        help_text="CSS font-family value, e.g. 'Inter', 'Poppins', 'system-ui'.",
    )
    base_font_size = models.PositiveSmallIntegerField(
        default=14,
        help_text="Base font size in px (e.g. 14, 16).",
    )

    # Text / accent
    heading_color = models.CharField(
        max_length=7,
        default="#111827",
        help_text="Default heading/title color.",
    )
    accent_color = models.CharField(
        max_length=7,
        default="#2563EB",
        help_text="Accent color for links, highlights, chips, etc.",
    )

    # Buttons (and navbar text)
    button_primary_bg = models.CharField(
        max_length=7,
        default="#102A54",
        help_text="Primary button background and navbar button background.",
    )
    button_primary_text = models.CharField(
        max_length=7,
        default="#FFFFFF",
        help_text="Primary button and navbar text color.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="If false, this brand is disabled for the client.",
    )

    def __str__(self):
        return self.company_name


# 🔹 OTP tokens for LOGIN (not for leads)
class LoginOTP(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["email", "created_at"]),
        ]

    def __str__(self):
        return f"{self.email} - {self.code} ({'used' if self.is_used else 'active'})"

    @classmethod
    def create_otp_for_email(cls, email: str, ttl_minutes: int = 5):
        """
        Single helper to generate + persist OTP.
        """
        code = f"{random.randint(0, 999999):06d}"
        now = timezone.now()
        obj = cls.objects.create(
            email=email.lower(),
            code=code,
            valid_until=now + timedelta(minutes=ttl_minutes),
        )
        return obj





# accounts/models.py

from django.db import models
from django.conf import settings
from clientsetup.models import Project  # jaha tumhara Project model hai

class ProjectUserAccess(models.Model):
    """
    Explicit project-level access per user.
    - Har row = "is user X allowed on project Y?"
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_accesses",
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="user_accesses",
    )

    # future ke liye flags (optional)
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("user", "project")]
        verbose_name = "Project User Access"
        verbose_name_plural = "Project User Accesses"

    def __str__(self):
        return f"{self.user} → {self.project} (active={self.is_active})"

