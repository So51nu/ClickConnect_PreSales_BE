# saleslead/models.py
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from clientsetup.models import Project   
from setup.models import UnitConfiguration
from accounts.models import User
from channel.models import ChannelPartnerProfile
from django.conf import settings
from django.db import models
# from django.contrib.postgres.fields import JSONField  
from django.core.exceptions import ValidationError


from django.db import models
from django.db.models import Q



class SiteVisitStatus(models.TextChoices):
    SCHEDULED = "SCHEDULED", "Scheduled"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    NO_SHOW = "NO_SHOW", "No Show"


class SiteVisitType(models.TextChoices):
    FIRST = "FIRST", "First Visit"
    REVISIT = "REVISIT", "Revisit"
    CLOSING = "CLOSING", "Closing / Negotiation"
    POSSESSION = "POSSESSION", "Possession / Handover"
    OTHER = "OTHER", "Other"


class SiteVisitOutcome(models.TextChoices):
    HOT = "HOT", "Hot – High Interest"
    WARM = "WARM", "Warm – Considering"
    COLD = "COLD", "Cold – Not Interested"
    HOLD = "HOLD", "Hold – Need Time"
    BOOKED = "BOOKED", "Booked / Converted"
    NO_DECISION = "NO_DECISION", "No Clear Decision"
    OTHER = "OTHER", "Other"




class LeadOpportunityStatusConfigManager(models.Manager):
    def for_project(self, project_id: int):
        """
        Project ke liye saare configs (project-specific + global).
        """
        return (
            self.get_queryset()
            .filter(
                Q(project_id=project_id) | Q(project__isnull=True),
                is_active=True,
            )
            .order_by("-project_id", "code")  # project-specific first
        )

    def effective_for_project(self, project_id: int):
        """
        Har code ka sirf ek effective config (project-specific > global).
        """
        qs = (
            self.get_queryset()
            .filter(
                Q(project_id=project_id) | Q(project__isnull=True),
                is_active=True,
            )
            .order_by("-project_id", "code")
        )

        by_code = {}
        for cfg in qs:
            if cfg.code not in by_code:
                by_code[cfg.code] = cfg
        return list(by_code.values())


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


def sales_lead_proposal_upload_to(instance, filename):
    return f"sales_leads/{instance.sales_lead_id}/proposal/{filename}"


def sales_lead_document_upload_to(instance, filename):
    return f"sales_leads/{instance.sales_lead_id}/docs/{filename}"

from django.db import models
from django.conf import settings
from django.utils import timezone
from clientsetup.models import Project
User = settings.AUTH_USER_MODEL


class LeadSourceSystem(models.TextChoices):
    META = "META", "Meta / Facebook Ads"
    GOOGLE_SHEET = "GOOGLE_SHEET", "Google Sheet"
    GOOGLE_ADS = "GOOGLE_ADS", "Google Ads"
    WEB_FORM = "WEB_FORM", "Website Form"
    PORTAL = "PORTAL", "Property Portal"     # MagicBricks / 99acres / Housing
    WHATSAPP = "WHATSAPP", "WhatsApp"
    CHATBOT = "CHATBOT", "Chatbot"
    CALLING = "CALLING", "Calling Data Upload" 
    OTHER = "OTHER", "Other / Manual Import"
    DIGITAL="DIGITAL","Digital"
    DIRECT="DIRECT","Direct/Walk-In"
    CHANNEL_PARTNER="CHANNER_PARTNER","Channel Partner"


class LeadOpportunityStatus(models.TextChoices):
    NEW = "NEW", "New (not reviewed)"
    IN_REVIEW = "IN_REVIEW", "In Review"
    CONVERTED = "CONVERTED", "Converted to Lead"
    JUNK = "JUNK", "Marked as Junk"
    DUPLICATE = "DUPLICATE", "Duplicate / Merged"
    RINGIING_BUSY="RINGING_BUSY","RINGIING/BUSY"
    DETAILS_="DETAILS","DETAILS SHARED"
    SV_LINEUP="SV_LINEUP","SV LINE UP"
    SV_DONE="SV_DONE","SV DONE"
    RV_DONE="RV_DONE","RV DONE"
    NOT_INTERESTED="NOT_INTERESTED","NOT INTERESTED"
    LOW_BUDGET = "LOW_BUDGET","LOW BUDGET"
    READY_TO_MOVE_IN = "READY_TO_MOVE_IN","READY TO MOVE IN"
    NEAR_POSSESSION="NEAR_POSSESSION","NEAR POSSESSION"
    OTHERS="OTHERS","OTHERS"



class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LeadOpportunityStatusConfig(models.Model):
    """
    Per-project configuration for opportunity statuses.

    Each row defines, for a given project + status code,
    whether moving an opportunity to this status should
    automatically convert it into a SalesLead.
    """

    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="opportunity_status_configs",
        help_text="If null, this status config is global and can be used for all projects.",
    )

    # same codes as your LeadOpportunityStatus TextChoices (e.g. NEW, IN_REVIEW, JUNK, etc.)
    code = models.CharField(
        max_length=20,
        choices=LeadOpportunityStatus.choices,
        help_text="Status code stored on LeadOpportunity.status.",
    )


    label = models.CharField(
        max_length=100,
        help_text="Human readable label to show in the UI.",
    )

    can_convert = models.BooleanField(
        default=False,
        help_text=(
            "If true, when an opportunity is moved to this status "
            "we will automatically create a SalesLead from it "
            "(if it's not already converted)."
        ),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunity_status_configs_created",
    )

    is_active = models.BooleanField(default=True)
    objects = LeadOpportunityStatusConfigManager()  
    class Meta:
        verbose_name = "Lead Opportunity Status Config"
        verbose_name_plural = "Lead Opportunity Status Configs"
        unique_together = [
            ("project", "code"),
        ]

    def __str__(self):
        if self.project:
            project_name = (
                getattr(self.project, "project_name", None)  # agar kabhi future me ho
                or getattr(self.project, "name", None)       # current model ka field
                or str(self.project)                         # fallback __str__
            )
        else:
            project_name = "GLOBAL"

        return f"{self.label} [{self.code}] ({project_name})"


class LeadOpportunity(TimeStamped):
    """
    Raw incoming 'opportunity' from Meta, Google Sheet, website, portals, etc.
    Dedupe is by (source_system, external_id).
    """

    source_system = models.CharField(
        max_length=50,
        choices=LeadSourceSystem.choices,
        default=LeadSourceSystem.OTHER,
        help_text="From where this opportunity came (Meta, Sheet, Web, Portal, etc.).",
    )
    # e.g. 'MagicBricks', '99acres', 'Landing Page - Tower A', 'FB Campaign 1'
    source_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional: sheet name, form name, portal name, campaign name etc.",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_opportunities_owned",
        help_text="User responsible for this opportunity.",
    )



    # ID from source platform (leadgen_id, sheet row id, portal lead id...)
    external_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID from Meta / form / sheet row / portal, used for de-duplication.",
    )

    import_batch_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Batch id for imports (e.g. one Google Sheet upload).",
    )

    status = models.CharField(
        max_length=20,
        choices=LeadOpportunityStatus.choices,
        default=LeadOpportunityStatus.NEW,
    )

    status_config = models.ForeignKey(
        "LeadOpportunityStatusConfig",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunities",
        help_text="Resolved status configuration (project specific / global) for this opportunity.",
    )

    # --- loose contact info (raw) ---
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    mobile_number = models.CharField(max_length=32, blank=True)

    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_opportunities",
        help_text="Project detected from sheet/meta/portal mapping (optional).",
    )

    raw_payload = models.JSONField(
        blank=True,
        null=True,
        help_text="Full raw JSON/body from the source for debugging and re-parsing.",
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_opportunities_created",
    )

    class Meta:
        indexes = [
            models.Index(fields=["source_system"]),
            models.Index(fields=["external_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["project"]),
        ]
        unique_together = [
            ("source_system", "external_id"),
        ]
        verbose_name = "Lead Opportunity"
        verbose_name_plural = "Lead Opportunities"

    def __str__(self):
        base = self.full_name or self.mobile_number or self.email or f"#{self.pk}"
        return f"Opportunity {base} ({self.source_system})"

    def clean(self):
        pass


class LeadOpportunityAttachment(TimeStamped):
    opportunity = models.ForeignKey(
        LeadOpportunity,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="opportunity_calling_data/")
    kind = models.CharField(
        max_length=50,
        default="CALLING_DATA",  
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # created_by = models.ForeignKey(
    #     settings.AUTH_USER_MODEL,
    #     null=True,
    #     blank=True,
    #     on_delete=models.SET_NULL,
    # )
    notes = models.TextField(null=True,blank=True)


class LeadOpportunityStatusHistory(TimeStamped):
    """
    History of status_config changes for an opportunity.
    Status code hamesha status_config.code se mil sakta hai, isliye
    old_status/new_status fields ki zaroorat nahi hai.
    """

    opportunity = models.ForeignKey(
        LeadOpportunity,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    old_status_config = models.ForeignKey(
        LeadOpportunityStatusConfig,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="old_status_histories",
    )

    new_status_config = models.ForeignKey(
        LeadOpportunityStatusConfig,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="new_status_histories",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_opportunity_status_changes",
    )

    comment = models.TextField(blank=True)

    auto_converted = models.BooleanField(default=False)

    sales_lead = models.ForeignKey(
        "SalesLead",   # same app me SalesLead hai to ye chalega
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunity_status_changes",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lead Opportunity Status History"
        verbose_name_plural = "Lead Opportunity Status Histories"

    def __str__(self):
        return f"History for Opportunity #{self.opportunity_id}"


class SalesLead(TimeStamped):
    """
    Single source of truth for a lead.
    Project-scoped via project; keeps contact, taxonomy, assignment, and product info.
    """
    class Nationality(models.TextChoices):
        INDIAN = "INDIAN", "Indian"
        NRI    = "NRI",    "NRI"
        OTHER  = "OTHER",  "Others"

    class AgeGroup(models.TextChoices):
        LT_20   = "LT20",  "<20"
        G20_25  = "20_25", "20-25"
        G26_35  = "26_35", "26-35"
        G36_45  = "36_45", "36-45"
        G46_60  = "46_60", "46-60"
        GT_60   = "GT60",  ">60"

    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name  = models.CharField(max_length=150, null=True, blank=True)

    # Direct FK to Project
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="sales_leads",
    )

    last_site_visit_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ("SCHEDULED", "Scheduled"),
            ("COMPLETED", "Completed"),
            ("CANCELLED", "Cancelled"),
            ("NO_SHOW", "No Show")
        ]
    )

    nationality = models.CharField(
        max_length=16,
        choices=Nationality.choices,
        null=True,
        blank=True,
        help_text="Indian / NRI / Others as per customer form.",
    )

    age_group = models.CharField(
        max_length=16,
        choices=AgeGroup.choices,
        null=True,
        blank=True,
        help_text="Age bracket like 20-25, 26-35, etc.",
    )
    # ---------- Requirement: unit configuration ----------
    unit_configuration = models.ForeignKey(
        UnitConfiguration,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
        help_text="2 BHK / 3 BHK / 4 BHK (Jodi) etc.",
    )

    last_site_visit_at = models.DateTimeField(null=True, blank=True)

    channel_partner = models.ForeignKey(
        ChannelPartnerProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
        help_text="If this lead came via a registered Channel Partner",
    )

    unknown_channel_partner = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="CP / broker / agency name if not registered in system",
    )


    walking = models.BooleanField(
        default=False,
        help_text="True if this lead is a walk-in (direct) lead.",
    )

    email         = models.EmailField(null=True,blank=True,unique=False)
    mobile_number = models.CharField(max_length=32, blank=True)
    tel_res       = models.CharField(max_length=32,null=True, blank=True)
    tel_office    = models.CharField(max_length=32,null=True,  blank=True)

    company       = models.CharField(max_length=150,null=True,  blank=True)
    budget        = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    annual_income = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    classification = models.ForeignKey(
        "leadmanage.LeadClassification", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_leads_primary"
    )
    sub_classification = models.ForeignKey(
        "leadmanage.LeadClassification", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_leads_secondary"
    )
    source = models.ForeignKey(
        "leadmanage.LeadSource", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_leads_source"
    )
    sub_source = models.ForeignKey(
        "leadmanage.LeadSource", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_leads_sub_source"
    )
    status = models.ForeignKey(
        "leadmanage.LeadStatus", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_leads_status"
    )
    sub_status = models.ForeignKey(
        "leadmanage.LeadSubStatus", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_leads_sub_status"
    )
    purpose = models.ForeignKey(
        "leadmanage.LeadPurpose", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_leads_purpose"
    )

    current_owner = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="owned_sales_leads"
    )

    first_owner = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="first_owned_sales_leads"
    )

    assign_to = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_sales_leads_next"
    )

    offering_types = models.ManyToManyField(
        "setup.OfferingType",null=True,  blank=True, related_name="sales_leads"
    )

    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="Lead_created"
    )

    source_opportunity = models.OneToOneField(
        "salelead.LeadOpportunity",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_lead",
        help_text="If this SalesLead was created from an imported LeadOpportunity.",
    )
    class Meta:
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["current_owner"]),
            models.Index(fields=["status"]),
            models.Index(fields=["channel_partner"]),  # for CP reporting
            models.Index(fields=["walking"]),          # for walk-in filters
        ]

    def get_full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def __str__(self):
        name = (self.first_name or "") + (" " + self.last_name if self.last_name else "")
        ident = name.strip() or self.email or self.mobile_number or f"#{self.pk}"
        return f"SalesLead {ident}"

    def _proj_id(self):
        return getattr(self, "project_id", None)

    def clean(self):
        # --- classification/source parent-child checks ---
        if self.sub_classification_id and self.classification_id:
            if self.sub_classification.parent_id != self.classification_id:
                raise ValidationError("sub_classification must be a child of classification.")

        if self.sub_source_id and self.source_id:
            if self.sub_source.parent_id != self.source_id:
                raise ValidationError("sub_source must be a child of source.")

        pid = self._proj_id()
        for f in ("classification", "sub_classification", "source", "sub_source",
                  "status", "sub_status", "purpose"):
            obj = getattr(self, f, None)
            if not obj:
                continue
            obj_pid = getattr(obj, "project_id", getattr(getattr(obj, "status", None), "project_id", None))
            if obj_pid != pid:
                raise ValidationError(f"{f} must belong to the same project.")

        # --- CP consistency ---
        if self.channel_partner_id and self.unknown_channel_partner:
            raise ValidationError(
                "Use either 'channel_partner' or 'unknown_channel_partner', not both."
            )


class SalesLeadStatusHistory(TimeStamped):
    """
    Keeps a timeline of status changes for a lead.
    One row per change.
    """
    sales_lead = models.ForeignKey(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    old_status = models.ForeignKey(
        "leadmanage.LeadStatus",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="status_history_from",
    )
    new_status = models.ForeignKey(
        "leadmanage.LeadStatus",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="status_history_to",
    )

    old_sub_status = models.ForeignKey(
        "leadmanage.LeadSubStatus",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sub_status_history_from",
    )
    new_sub_status = models.ForeignKey(
        "leadmanage.LeadSubStatus",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sub_status_history_to",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_status_changes",
    )

    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Lead #{self.sales_lead_id} | {self.old_status} → {self.new_status}"


class SalesLeadAddress(TimeStamped):
    sales_lead = models.OneToOneField(SalesLead, on_delete=models.CASCADE, related_name="address")
    flat_or_building = models.CharField(max_length=120, blank=True)
    area    = models.CharField(max_length=120, blank=True)
    pincode = models.CharField(max_length=20,  blank=True)
    city    = models.CharField(max_length=80,  blank=True)
    state   = models.CharField(max_length=80,  blank=True)
    country = models.CharField(max_length=80,  blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"Address for SalesLead #{self.sales_lead_id}"


class SalesLeadCPInfo(TimeStamped):
    """
    CP Information section:
      - Referral code
      - Which CP user (if any) owns this lead
    """
    sales_lead = models.OneToOneField(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="cp_info",
    )

    cp_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="cp_sales_leads",
    )

    referral_code = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"CP info for SalesLead #{self.sales_lead_id}"


class SalesLeadPersonalInfo(TimeStamped):
    """
    Extra personal details (Additional Information section in UI).
    Address stays in SalesLeadAddress.
    """
    sales_lead = models.OneToOneField(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="personal_info",
    )

    # Dates
    date_of_birth = models.DateField(null=True, blank=True)
    date_of_anniversary = models.DateField(null=True, blank=True)

    # Already a part of the family?
    already_part_of_family = models.BooleanField(default=False)

    # Extra contact details
    secondary_email   = models.EmailField(blank=True)
    alternate_mobile  = models.CharField(max_length=32, blank=True)
    alternate_tel_res = models.CharField(max_length=32, blank=True)
    alternate_tel_off = models.CharField(max_length=32, blank=True)

    visiting_on_behalf = models.ForeignKey(
        "leadmanage.VisitingHalf",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
    )
    current_residence_ownership = models.ForeignKey(
        "leadmanage.ResidencyOwnerShip",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
    )
    # In UI: "Current Residence type" – keeping as free text
    current_residence_type = models.CharField(max_length=120, blank=True)

    family_size = models.ForeignKey(
        "leadmanage.FamilySize",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
    )
    possession_desired_in = models.ForeignKey(
        "leadmanage.PossienDesigned",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
    )

    # Social links
    facebook = models.URLField(blank=True)
    twitter  = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)

    def __str__(self):
        return f"Personal info for SalesLead #{self.sales_lead_id}"


class SalesLeadProfessionalInfo(TimeStamped):
    """
    Professional Information section in the UI.
    """
    sales_lead = models.OneToOneField(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="professional_info",
    )

    occupation = models.ForeignKey(
        "leadmanage.Occupation",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
    )
    organization_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the organization",
    )
    office_location = models.CharField(
        max_length=255,
        blank=True,
    )
    office_pincode = models.CharField(
        max_length=20,
        blank=True,
    )
    designation = models.ForeignKey(
        "leadmanage.Designation",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_leads",
    )

    def __str__(self):
        return f"Professional info for SalesLead #{self.sales_lead_id}"


class SalesLeadProposalDocument(TimeStamped):
    """
    Attachments under 'Proposal Form' section.
    Allows multiple files per lead.
    """
    sales_lead = models.ForeignKey(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="proposal_documents",
    )
    file = models.FileField(upload_to=sales_lead_proposal_upload_to)

    def __str__(self):
        return f"Proposal doc for SalesLead #{self.sales_lead_id}"



class SalesLeadUpdateStatus(models.Model):
    """
    Configurable status for SalesLeadUpdate activities.
    Example values:
      - code: "PENDING",  label: "Pending"
      - code: "DONE",     label: "Done"
      - code: "SKIPPED",  label: "Skipped"
    """
    project=models.ForeignKey(Project,on_delete=models.CASCADE)
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label


class SalesLeadUpdate(TimeStamped):
    TYPE_CHOICES = [
        ("FOLLOW_UP", "Follow Up"),
        ("REMINDER", "Reminder"),
        ("NOTE", "Note"),	        ("SITE_VISIT", "Site Visit"),
        ("WHATSAPP", "WhatsApp Message"),
        ("EMAIL", "Email"),
        ("STATUS_CHANGE", "Status Change"),
        ("CALL", "Call Log"),
        ("OTHER", "Other"),
    ]
    reminder_sent_at = models.DateTimeField(null=True, blank=True)

    sales_lead = models.ForeignKey(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="updates"
    )

    activity_status = models.ForeignKey(
        SalesLeadUpdateStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="updates",
    )


    update_type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default="NOTE"
    )

    title = models.CharField(max_length=150)
    info = models.TextField(blank=True)
    event_date = models.DateTimeField(default=timezone.now)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_lead_updates_created"
    )
    reminder_log = models.JSONField(
        default=dict,
        blank=True,
        help_text="Map of offset_minutes → ISO datetime when reminder was sent.",
    )

    class Meta:
        ordering = ["-event_date", "-id"]

    def __str__(self):
        return f"LeadUpdate({self.update_type}) → {self.title}"


class SalesLeadUpdateStatusHistory(TimeStamped):
    """
    History of activity_status changes for a SalesLeadUpdate.
    """
    sales_lead_update = models.ForeignKey(
        SalesLeadUpdate,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status = models.ForeignKey(
        SalesLeadUpdateStatus,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    new_status = models.ForeignKey(
        SalesLeadUpdateStatus,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_lead_update_status_changes",
    )
    comment = models.TextField(blank=True)

    # optional explicit timestamp if you don’t want to rely only on created_at
    event_date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-event_date", "-id"]

    def __str__(self):
        return f"UpdateStatusHistory({self.old_status} → {self.new_status})"
    

class SalesLeadStageHistory(TimeStamped):
    sales_lead = models.ForeignKey(SalesLead, on_delete=models.CASCADE, related_name="stage_history")
    stage = models.ForeignKey("leadmanage.LeadStage", on_delete=models.PROTECT, related_name="stage_entries")
    status = models.ForeignKey("leadmanage.LeadStatus", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="status_entries")
    sub_status = models.ForeignKey("leadmanage.LeadSubStatus", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="sub_status_entries")
    event_date = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="sales_lead_stage_histories_created"
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-event_date", "-id"]
        indexes = [models.Index(fields=["sales_lead", "event_date"]), models.Index(fields=["stage"])]

    def __str__(self):
        return f"{self.sales_lead_id} → {self.stage.name} @ {self.event_date:%Y-%m-%d}"

    def clean(self):
        if self.sub_status_id and self.status_id:
            if self.sub_status.status_id != self.status_id:
                raise ValidationError("sub_status must be under the selected status.")


class SalesLeadDocument(TimeStamped):
    sales_lead = models.ForeignKey(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    title = models.CharField(max_length=150,null=True, blank=True)
    file = models.FileField(upload_to=sales_lead_document_upload_to)

    def __str__(self):
        return f"LeadDoc[{self.sales_lead_id}] {self.title or self.file.name}"


class InterestedLeadUnit(TimeStamped):
    sales_lead = models.ForeignKey(
        "salelead.SalesLead",
        on_delete=models.CASCADE,
        related_name="interested_unit_links",
    )
    unit = models.ForeignKey(
        "clientsetup.Unit",
        on_delete=models.CASCADE,
        related_name="lead_interest_links",
    )
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ("sales_lead", "unit")

    def __str__(self):
        return f"Lead #{self.sales_lead_id} → Unit #{self.unit_id}"


class EmailType(models.TextChoices):
    WELCOME   = "WELCOME", "Welcome / Acknowledgement"
    FOLLOWUP  = "FOLLOWUP", "Follow-up"
    REMINDER  = "REMINDER", "Reminder"
    QUOTATION = "QUOTATION", "Quotation / Cost Sheet"
    OTHER     = "OTHER", "Other"


class EmailStatus(models.TextChoices):
    DRAFT   = "DRAFT", "Draft"
    QUEUED  = "QUEUED", "Queued"
    SENT    = "SENT", "Sent"
    FAILED  = "FAILED", "Failed"


class SalesLeadEmailLog(models.Model):
    """
    Kis lead ko, kab, kisne email bheji – tracking table.

    Har row = ek email event:
      - lead + subject + body snapshot
      - sent_by (user)
      - status + timestamps
    """

    sales_lead = models.ForeignKey(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="email_logs",
        help_text="Jis lead ko email gayi.",
    )

    # Basic email info
    email_type = models.CharField(
        max_length=20,
        choices=EmailType.choices,
        default=EmailType.OTHER,
        help_text="Email ka purpose / category.",
    )
    subject = models.CharField(max_length=255)
    body = models.TextField(help_text="Email body ka snapshot jab bheji gayi.")

    # Addresses
    to_email = models.EmailField(help_text="Lead ko bheji gayi email address.")
    cc = models.TextField(
        blank=True,
        help_text="Comma-separated CC emails (optional).",
    )
    bcc = models.TextField(
        blank=True,
        help_text="Comma-separated BCC emails (optional).",
    )
    from_email = models.EmailField(
        blank=True,
        help_text="Jo 'from' address use hua (SMTP / SendGrid, etc.).",
    )
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_lead_emails",
        help_text="Jo user ne trigger kiya (ya null agar system ne bheja).",
    )

    status = models.CharField(
        max_length=10,
        choices=EmailStatus.choices,
        default=EmailStatus.DRAFT,
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Jab actual mail provider ko bheja gaya.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sales Lead Email Log"
        verbose_name_plural = "Sales Lead Email Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sales_lead", "created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Email[{self.id}] to {self.to_email} ({self.status})"


class LeadComment(models.Model):
    sales_lead = models.ForeignKey(
        "salelead.SalesLead",              # app/model name adjust karo if different
        on_delete=models.CASCADE,
        related_name="comments",
    )

    text = models.TextField()

    # yaha FK to leadmanage.LeadStage
    stage_at_time = models.ForeignKey(
        "leadmanage.LeadStage",            # app_label.ModelName
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_comments",
        help_text="Stage of this lead when the comment was added",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_comments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment #{self.id} on lead #{self.sales_lead_id}"



class SiteVisit(models.Model):
    # ---------- Link to Lead / Project / CP ----------
    lead = models.ForeignKey(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="site_visits",
        help_text="Primary lead for whom this visit is scheduled.",
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="site_visits",
    )

    # Optional: which channel partner brought this visit
    channel_partner = models.ForeignKey(
        "channel.ChannelPartnerProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visits",
        help_text="Channel partner responsible (if any).",
    )

    # ---------- Visit meta ----------
    visit_type = models.CharField(
        max_length=20,
        choices=SiteVisitType.choices,
        default=SiteVisitType.FIRST,
        help_text="Type of visit – first, revisit, closing etc.",
    )

    visit_number = models.PositiveIntegerField(
        default=1,
        help_text="1 = first visit for this lead, 2 = second visit, etc.",
    )

    # eg. Sales stage at the time of scheduling (optional)
    lead_stage = models.ForeignKey(
        "leadmanage.LeadStage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visits",
        help_text="Lead stage at the time of this visit (optional).",
    )

    # ---------- Visitor details ----------
    member_name = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        help_text="Name of the main visitor (if different from lead).",
    )

    member_mobile_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Mobile number of the visiting member.",
    )

    member_count = models.PositiveIntegerField(
        default=1,
        help_text="Total people expected in the visit (lead + family).",
    )

    # ---------- Unit / inventory ----------
    unit_config = models.ForeignKey(
        "setup.UnitConfiguration",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visits",
    )

    inventory = models.ForeignKey(
        "clientsetup.Inventory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visits",
    )

    # ---------- Scheduling / actual timings ----------
    scheduled_at = models.DateTimeField(
        help_text="Planned date & time for the visit.",
    )

    scheduled_end_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Planned end time (for better planning & reporting).",
    )

    actual_start_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual check-in time at site.",
    )

    actual_end_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual check-out time.",
    )

    # ---------- Status / cancellation / no-show ----------
    status = models.CharField(
        max_length=20,
        choices=[
            ("SCHEDULED", "Scheduled"),
            ("RESCHEDULED", "Rescheduled"),   # 👈 NEW
            ("COMPLETED", "Completed"),
            ("CANCELLED", "Cancelled"),
            ("NO_SHOW", "No Show"),
        ],
        default="SCHEDULED",
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the visit was cancelled (if status=CANCELLED).",
    )
    cancelled_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Free text reason for cancellation.",
    )

    no_show_reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason if customer did not show up (status=NO_SHOW).",
    )

    # ---------- Outcome / feedback ----------
    outcome = models.CharField(
        max_length=20,
        choices=SiteVisitOutcome.choices,
        null=True,
        blank=True,
        help_text="Post-visit outcome / interest level.",
    )

    outcome_notes = models.TextField(
        null=True,
        blank=True,
        help_text="Detailed notes / summary of discussion, objections, requirements.",
    )

    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Optional 1–5 rating for interest / seriousness.",
    )

    # ---------- Reminder tracking ----------
    reminder_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last reminder sent datetime.",
    )

    reminder_count = models.PositiveIntegerField(
        default=0,
        help_text="How many reminders were sent.",
    )

    next_reminder_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, Celery/cron can use this to plan next reminder.",
    )

    # ---------- Location / logistics ----------
    location_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Eg. 'Site Office', 'Sample Flat - Tower A', etc.",
    )

    meeting_address = models.TextField(
        blank=True,
        help_text="Full address if different from default project address.",
    )

    reminder_log = models.JSONField(
        default=dict,
        blank=True,
        help_text="Map of offset_minutes → ISO datetime when reminder was sent.",
    )

    google_maps_link = models.URLField(
        max_length=500,
        blank=True,
        help_text="Google Maps link for the meeting point (optional).",
    )

    pickup_required = models.BooleanField(
        default=False,
        help_text="Whether cab / pickup is required.",
    )

    pickup_details = models.TextField(
        blank=True,
        help_text="Cab details, driver number, pickup point etc.",
    )

    # ---------- Audit / notes ----------
    public_notes = models.TextField(
        blank=True,
        help_text="General notes visible to sales team.",
    )

    internal_notes = models.TextField(
        blank=True,
        help_text="Internal notes (not to be shared with customer).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="site_visits_created",
    )

    updated_at = models.DateTimeField(auto_now=True)

    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visits_updated",
    )

    class Meta:
        indexes = [
            models.Index(fields=["lead"]),
            models.Index(fields=["project"]),
            models.Index(fields=["status"]),
            models.Index(fields=["scheduled_at"]),
            models.Index(fields=["actual_start_at"]),
            models.Index(fields=["outcome"]),
        ]
        ordering = ["-scheduled_at", "-id"]

    def __str__(self):
        return f"SiteVisit #{self.id} for Lead {self.lead_id} ({self.status})"


class SiteVisitRescheduleHistory(models.Model):
    site_visit = models.ForeignKey(
        SiteVisit,
        on_delete=models.CASCADE,
        related_name="reschedule_history",
    )
    old_scheduled_at = models.DateTimeField()
    new_scheduled_at = models.DateTimeField()
    reason = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visit_reschedules_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']



from datetime import timedelta
from django.utils import timezone

class LeadEmailOTP(models.Model):
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["email", "is_verified"]),
        ]

    def __str__(self):
        return f"OTP for {self.email} ({self.otp_code})"






# salelead/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

from clientsetup.models import Project
from booking.models import Booking   # agar booking app hai
from accounts.models import User


def payment_pos_upload_to(instance, filename):
    return f"sales_leads/{instance.lead_id}/payments/pos/{filename}"


def payment_cheque_upload_to(instance, filename):
    return f"sales_leads/{instance.lead_id}/payments/cheque/{filename}"


class PaymentLead(models.Model):
    class PaymentType(models.TextChoices):
        EOI     = "EOI", "EOI"
        BOOKING = "BOOKING", "Booking"

    class PaymentMethod(models.TextChoices):
        ONLINE      = "ONLINE", "Online"
        POS         = "POS", "POS"
        DRAFT_CHEQUE = "DRAFT_CHEQUE", "Draft / Cheque"
        NEFT_RTGS   = "NEFT_RTGS", "NEFT / RTGS"

    class PaymentStatus(models.TextChoices):
        PENDING  = "PENDING", "Pending"
        SUCCESS  = "SUCCESS", "Success"
        FAILED   = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    # ---------- Relations ----------
    lead = models.ForeignKey(
        "salelead.SalesLead",
        on_delete=models.CASCADE,
        related_name="payments",
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="lead_payments",
        help_text="Denormalised from SalesLead.project for faster filters.",
    )

    booking = models.ForeignKey(
        Booking,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_payments",
        help_text="Optional link to final booking, if created.",
    )

    for_kyc = models.BooleanField(
        default=False,
        help_text="If true, this payment is only for KYC and should not be shown in normal payment flows.",
    )

    kyc_request = models.ForeignKey(
        "booking.BookingKycRequest",   # app_label.ModelName
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payments",
        help_text="If this payment is specifically for a Booking KYC request.",
    )


    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="lead_payments_created",
    )

    # ---------- Core payment info ----------
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    payment_date = models.DateTimeField(
        default=timezone.now,
        help_text="When payment was received / initiated.",
    )

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    notes = models.TextField(
        null=True,
        blank=True,
    )

    # ---------- ONLINE / POS common ----------
    payment_mode = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="For ONLINE/POS: UPI, Card, NetBanking, Wallet, etc.",
    )

    transaction_no = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="PG transaction id / POS transaction no.",
    )

    # ---------- POS only ----------
    pos_slip_image = models.ImageField(
        upload_to=payment_pos_upload_to,
        null=True,
        blank=True,
        help_text="Image of POS charge slip.",
    )

    # ---------- DRAFT / CHEQUE ----------
    cheque_number = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    cheque_date = models.DateField(
        null=True,
        blank=True,
    )

    bank_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    ifsc_code = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    branch_name = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    cheque_image = models.ImageField(
        upload_to=payment_cheque_upload_to,
        null=True,
        blank=True,
        help_text="Scanned cheque image.",
    )

    # ---------- NEFT / RTGS ----------
    neft_rtgs_ref_no = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="NEFT / RTGS reference number.",
    )

    class Meta:
        ordering = ["-payment_date", "-id"]
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["lead"]),
            models.Index(fields=["payment_type"]),
            models.Index(fields=["payment_method"]),
            models.Index(fields=["status"]),
            models.Index(fields=["for_kyc"]),
        ]

    def __str__(self):
        return f"PaymentLead #{self.pk} - Lead #{self.lead_id} - {self.amount}"

    def clean(self):
        """
        Optional: method-wise validations so BE strictly follow your FE form:
        - ONLINE/POS => transaction_no required
        - CHEQUE => cheque_number, cheque_date, bank_name, ifsc_code, branch_name required
        - NEFT_RTGS => neft_rtgs_ref_no required
        """
        from django.core.exceptions import ValidationError

        # Basic amount check
        if self.amount is not None and self.amount <= Decimal("0"):
            raise ValidationError("Amount must be greater than 0.")

        # Method-specific requirements
        if self.payment_method in [self.PaymentMethod.ONLINE, self.PaymentMethod.POS]:
            if not self.transaction_no:
                raise ValidationError("Transaction No is required for ONLINE/POS payments.")

        if self.payment_method == self.PaymentMethod.DRAFT_CHEQUE:
            missing = []
            if not self.cheque_number:
                missing.append("Cheque Number")
            if not self.cheque_date:
                missing.append("Cheque Date")
            if not self.bank_name:
                missing.append("Bank Name")
            if not self.ifsc_code:
                missing.append("IFSC Code")
            if not self.branch_name:
                missing.append("Branch Name")
            if missing:
                raise ValidationError(f"Missing cheque fields: {', '.join(missing)}")

        if self.payment_method == self.PaymentMethod.NEFT_RTGS:
            if not self.neft_rtgs_ref_no:
                raise ValidationError("NEFT / RTGS Ref.No is required for NEFT/RTGS payments.")










class SalesLeadChangeLog(TimeStamped):
    """
    Generic audit log for SalesLead.

    - Har change me:
      - action: kya hua (CREATE / UPDATE / STATUS_CHANGE / OWNER_CHANGE / NOTE / OTHER)
      - snapshot_before: change ke pehle ka full view
      - snapshot_after: change ke baad ka full view
      - changes: normalized diff (field-wise) for easy UI
      - comment: koi extra remark (UI se aaya ho)
    """

    class Action(models.TextChoices):
        CREATE         = "CREATE", "Create"
        UPDATE         = "UPDATE", "Update"
        STATUS_CHANGE  = "STATUS_CHANGE", "Status Change"
        OWNER_CHANGE   = "OWNER_CHANGE", "Owner Change"
        NOTE           = "NOTE", "Note / Comment"
        OTHER          = "OTHER", "Other"

    sales_lead = models.ForeignKey(
        SalesLead,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )

    action = models.CharField(
        max_length=32,
        choices=Action.choices,
        default=Action.UPDATE,
    )

    # BEFORE / AFTER snapshot of full lead (normalized dict)
    snapshot_before = models.JSONField(null=True, blank=True)
    snapshot_after  = models.JSONField(null=True, blank=True)

    # Normalized diff list for UI:
    # [
    #   {"path": "contact.mobile_number", "label": "Mobile Number", "old": "9xxx", "new": "8xxx"},
    #   ...
    # ]
    changes = models.JSONField(null=True, blank=True)

    comment = models.TextField(blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="saleslead_change_logs",
    )

    # Optional: request metadata future ke liye (IP, UA etc.)
    request_meta = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"LeadChange #{self.id} | Lead #{self.sales_lead_id} | {self.action}"


def build_lead_snapshot(lead: "SalesLead") -> dict:
    """
    Ek normalized dict jo timeline & change log dono me use hoga.
    """

    address = getattr(lead, "address", None)
    cp_info = getattr(lead, "cp_info", None)

    def _user_dict(u):
        if not u:
            return None
        return {
            "id": u.id,
            "full_name": u.get_full_name() or u.username,
            "email": u.email,
        }

    def _obj_dict(obj, label_field="name"):
        if not obj:
            return None
        return {
            "id": obj.id,
            "name": getattr(obj, label_field, str(obj)),
        }

    return {
        "id": lead.id,
        "project": {
            "id": lead.project_id,
            "name": getattr(lead.project, "name", None) if hasattr(lead, "project") else None,
        },
        "identity": {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "full_name": lead.get_full_name(),
        },
        "contact": {
            "email": lead.email,
            "mobile_number": lead.mobile_number,
            "tel_res": lead.tel_res,
            "tel_office": lead.tel_office,
        },
        "company_profile": {
            "company": lead.company,
            "budget": str(lead.budget) if lead.budget is not None else None,
            "annual_income": str(lead.annual_income) if lead.annual_income is not None else None,
        },
        "taxonomy": {
            "classification": _obj_dict(lead.classification),
            "sub_classification": _obj_dict(lead.sub_classification),
            "source": _obj_dict(lead.source),
            "sub_source": _obj_dict(lead.sub_source),
            "status": _obj_dict(lead.status),
            "sub_status": _obj_dict(lead.sub_status),
            "purpose": _obj_dict(lead.purpose),
        },
        "ownership": {
            "current_owner": _user_dict(lead.current_owner),
            "first_owner": _user_dict(lead.first_owner),
            "assign_to": _user_dict(lead.assign_to),
        },
        "channel_partner": {
            "cp_profile": _obj_dict(lead.channel_partner, label_field="name"),
            "unknown_channel_partner": lead.unknown_channel_partner,
        },
        "cp_info": {
            "cp_user": _user_dict(getattr(cp_info, "cp_user", None)) if cp_info else None,
            "referral_code": getattr(cp_info, "referral_code", "") if cp_info else "",
        },
        "address": {
            "flat_or_building": getattr(address, "flat_or_building", "") if address else "",
            "area": getattr(address, "area", "") if address else "",
            "pincode": getattr(address, "pincode", "") if address else "",
            "city": getattr(address, "city", "") if address else "",
            "state": getattr(address, "state", "") if address else "",
            "country": getattr(address, "country", "") if address else "",
            "description": getattr(address, "description", "") if address else "",
        },
        "site_visit": {
            "last_site_visit_status": lead.last_site_visit_status,
            "last_site_visit_at": (
                lead.last_site_visit_at.isoformat() if lead.last_site_visit_at else None
            ),
        },
        "flags": {
            "walking": lead.walking,
        },
        "meta": {
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
            "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            "created_by": _user_dict(lead.created_by),
        },
    }

def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict:
    """
    {"a": {"b": 1}, "c": 2} -> {"a.b": 1, "c": 2}
    """
    items = {}
    for k, v in (d or {}).items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


FIELD_LABELS = {
    "identity.first_name": "First Name",
    "identity.last_name": "Last Name",
    "contact.email": "Email",
    "contact.mobile_number": "Mobile Number",
    "taxonomy.status.name": "Status",
    "taxonomy.sub_status.name": "Sub Status",
    "ownership.current_owner.full_name": "Current Owner",
    "channel_partner.cp_profile.name": "Channel Partner",
    "cp_info.referral_code": "Referral Code",
    "site_visit.last_site_visit_status": "Last Site Visit Status",
}


def build_lead_changes(before_snapshot: dict | None, after_snapshot: dict | None) -> list[dict]:
    """
    BEFORE/AFTER snapshot se normalized changes list.
    """
    if not before_snapshot and not after_snapshot:
        return []

    before_flat = _flatten_dict(before_snapshot or {})
    after_flat = _flatten_dict(after_snapshot or {})

    all_keys = set(before_flat.keys()) | set(after_flat.keys())
    changes = []

    for path in sorted(all_keys):
        old = before_flat.get(path)
        new = after_flat.get(path)
        if old == new:
            continue

        label = FIELD_LABELS.get(path, path)
        changes.append(
            {
                "path": path,
                "label": label,
                "old": old,
                "new": new,
            }
        )

    return changes


