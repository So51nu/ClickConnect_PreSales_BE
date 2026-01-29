# channel/models.py
from django.conf import settings
from django.db import models
from accounts.models import Role
from django.db.models.signals import post_save
from django.dispatch import receiver
from uuid import uuid4


User = settings.AUTH_USER_MODEL


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------- Masters ----------

class AgentType(TimeStamped):
    """
    Master: Agent Type (for Channel Partners)
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agent_types_created",
    )

    def __str__(self):
        return self.name


class PartnerTier(TimeStamped):
    """
    Master: Partner Tier (Global)
    """
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cp_tiers",
        limit_choices_to={"role": Role.ADMIN},
        help_text="Admin / builder who owns this tier config",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, unique=True)
    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Default CP commission % for this tier, e.g. 2.00 = 2%",
    )
    commission_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Flat commission amount per booking (optional)",
    )
    description = models.TextField(blank=True)
    is_global = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="partner_tiers_created",
    )

    def __str__(self):
        return f"{self.code} - {self.name}"


class CrmAuthType(models.TextChoices):
    API_KEY = "API_KEY", "API Key"
    OAUTH2 = "OAUTH2", "OAuth2"
    OTHER = "OTHER", "Other"


class CrmIntegration(TimeStamped):
    """
    Master: CRM Integrations (Salesforce, HubSpot, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    api_base_url = models.URLField(blank=True)
    auth_type = models.CharField(
        max_length=20,
        choices=CrmAuthType.choices,
        default=CrmAuthType.API_KEY,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="crm_integrations_created",
    )

    def __str__(self):
        return self.name


class OnboardingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"
    TERMINATED = "TERMINATED", "Terminated"


class PartnerStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class ChannelPartnerProfile(TimeStamped):
    """
    Extra business fields for a Channel Partner User (role = CP).
    One-to-one with accounts.User.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="channel_profile",
    )

    source = models.ForeignKey(
        "leadmanage.LeadSource",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="channel_partners",
        limit_choices_to={"for_cp": True},
        help_text="Lead source associated with this channel partner (CP only).",
    )


    referral_code = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Auto-generated referral code for this channel partner.",
    )

    # Hierarchy
    parent_agent = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_channel_partners",
        limit_choices_to={"role": "CHANNEL_PARTNER"},
        help_text="Parent Channel Partner (if any)",
    )

    # Masters
    agent_type = models.ForeignKey(
        AgentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="channel_partners",
    )
    partner_tier = models.ForeignKey(
        PartnerTier,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="channel_partners",
    )
    crm_integration = models.ForeignKey(
        CrmIntegration,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="channel_partners",
    )

    # Identity / KYC details
    mobile_number = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    pan_number = models.CharField(max_length=32, blank=True)
    gst_in = models.CharField(max_length=32, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    commission_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Free-text commission scheme description",
    )
    rera_number = models.CharField(max_length=64, blank=True)
    last_update_date = models.DateField(null=True, blank=True)

    # Program enrolment
    program_start_date = models.DateField(null=True, blank=True)
    program_end_date = models.DateField(null=True, blank=True)

    # Lead management & compliance
    enable_lead_sharing = models.BooleanField(default=False)
    regulatory_compliance_approved = models.BooleanField(default=False)

    # Operational setup
    onboarding_status = models.CharField(
        max_length=20,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.ACTIVE,
    )
    dedicated_support_contact_email = models.EmailField(blank=True)
    technical_setup_notes = models.TextField(blank=True)

    # Targets & scorecard
    annual_revenue_target = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    q1_performance_text = models.CharField(max_length=100, blank=True)

    # Overall partner status
    status = models.CharField(
        max_length=20,
        choices=PartnerStatus.choices,
        default=PartnerStatus.ACTIVE,
    )

    # Audit / who created / who last touched
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="channel_partners_created",
    )
    last_modified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="channel_partners_modified",
    )
    last_modified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Channel Partner: {self.user.get_full_name() or self.user.username}"





class ProjectAssignmentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ENDED = "ENDED", "Ended"
    PENDING = "PENDING", "Pending"


class ChannelPartnerProjectAuthorization(TimeStamped):
    """
    One row per (Channel Partner, Project).
    Drives Product Authorization toggles and list table.
    """
    channel_partner = models.ForeignKey(
        ChannelPartnerProfile,
        on_delete=models.CASCADE,
        related_name="project_authorizations",
    )
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="channel_partner_authorizations",
    )

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ProjectAssignmentStatus.choices,
        default=ProjectAssignmentStatus.ACTIVE,
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cp_project_auth_created",
    )

    class Meta:
        unique_together = ("channel_partner", "project")

    def __str__(self):
        return f"{self.channel_partner} -> {self.project} ({self.status})"


# ---------- Attachments (Business License etc.) ----------

class ChannelPartnerAttachment(TimeStamped):
    """
    Uploaded documents related to a Channel Partner (Business License, agreements, etc.)
    """
    BUSINESS_LICENSE = "BUSINESS_LICENSE"
    AGREEMENT = "AGREEMENT"
    OTHER = "OTHER"

    FILE_TYPE_CHOICES = (
        (BUSINESS_LICENSE, "Business License"),
        (AGREEMENT, "Agreement"),
        (OTHER, "Other"),
    )

    channel_partner = models.ForeignKey(
        ChannelPartnerProfile,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="channel_partner_docs/")
    file_type = models.CharField(
        max_length=50,
        choices=FILE_TYPE_CHOICES,
        default=OTHER,
    )
    description = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cp_attachments_created",
    )

    def __str__(self):
        return f"{self.channel_partner} - {self.get_file_type_display()}"
    

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.crypto import get_random_string


def generate_referral_code_for_cp(instance) -> str:
    """
    Pattern: CP + 6-digit zero-padded ID, e.g. CP000123
    """
    return f"CP{instance.pk:06d}"


@receiver(post_save, sender=ChannelPartnerProfile)
def auto_set_referral_code(sender, instance, created, **kwargs):
    """
    Jab naya ChannelPartnerProfile banta hai,
    agar referral_code blank hai toh auto-generate karo.
    """
    if not created:
        return

    # agar manually set kiya hai to respect karenge
    if instance.referral_code:
        return

    code = generate_referral_code_for_cp(instance)

    # safety: agar kabhi collision ho toh random wala use kar lenge
    attempts = 0
    while sender.objects.filter(referral_code=code).exists():
        attempts += 1
        if attempts > 5:
            # very unlikely, but fallback to random
            code = "CP" + get_random_string(8).upper()
            break
        code = "CP" + get_random_string(6).upper()

    sender.objects.filter(pk=instance.pk).update(referral_code=code)
    instance.referral_code = code

