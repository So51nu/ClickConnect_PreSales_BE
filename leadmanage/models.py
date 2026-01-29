# leadmange/models

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from setup.models import NamedLookup

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Currency(models.TextChoices):
    INR = "INR", "INR"
    USD = "USD", "USD"
    EUR = "EUR", "EUR"

class ReportType(models.TextChoices):
    SUMMARY  = "SUMMARY",  "Summary"
    DETAILED = "DETAILED", "Detailed"

class ExportFormat(models.TextChoices):
    CSV  = "CSV",  "CSV"
    XLSX = "XLSX", "Excel (XLSX)"
    PDF  = "PDF",  "PDF"

class Frequency(models.TextChoices):
    DAILY   = "DAILY",   "Daily"
    WEEKLY  = "WEEKLY",  "Weekly"
    MONTHLY = "MONTHLY", "Monthly"


def project_lead_logo_upload_to(instance, filename):
    return f"project_lead/{instance.project_id or 'new'}/logo/{filename}"


# =====================================================================
#             MASTER / LOOKUP (project-scoped hierarchical)
# =====================================================================

class LeadClassification(TimeStamped):
    """
    Hot / Warm / Cold, and infinite depth via parent -> children
    e.g. Hot -> (Interested - High Budget)
    """
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="lead_classifications",
    )
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.CASCADE, related_name="children"
    )

    class Meta:
        unique_together = ("project", "name", "parent")
        ordering = ["project__name", "parent__id", "name"]

    def __str__(self):
        chain = f"{self.parent.name} / " if self.parent_id else ""
        return f"{self.project.name} / {chain}{self.name}"

class LeadSource(TimeStamped):
    """
    Website -> (Google Search, Direct Traffic), Referral, Social Media, etc.
    Infinite parent/child, per project.
    """
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="lead_sources",
    )
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )

    # 🔹 Only for CP-related sources
    for_cp = models.BooleanField(
        default=False,
        help_text="Use this source for Channel Partners (CP) selection.",
    )

    for_walkin= models.BooleanField(
        default=False,
        help_text="Use this source for Channel Partners (CP) selection as Waling.",
    )

    class Meta:
        unique_together = ("project", "name", "parent")
        ordering = ["project__name", "parent__id", "name"]

    def __str__(self):
        chain = f"{self.parent.name} / " if self.parent_id else ""
        return f"{self.project.name} / {chain}{self.name}"

class LeadStage(TimeStamped):
    project = models.ForeignKey("clientsetup.Project", on_delete=models.CASCADE, related_name="lead_stages")
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=1, db_index=True)
    is_closed = models.BooleanField(default=False)
    is_won = models.BooleanField(default=False)

    for_site = models.BooleanField(
        default=False,
        help_text="If true, this stage is used for site / walk-in tracking.",
    )

    class Meta:
        unique_together = ("project", "name")
        ordering = ["project__name", "order"]

    def __str__(self):
        return f"{self.project.name} / {self.order}. {self.name}"

    def clean(self):

        qs = LeadStage.objects.filter(project=self.project)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.count() >= 8:
            raise ValidationError("Only 8 lead stages are allowed per project.")


class LeadStatus(TimeStamped):
    """
    Status taxonomy separate from stages (e.g. Open, On Hold, Closed),
    project-scoped, hierarchical is optional (see LeadSubStatus).
    """
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="lead_statuses",
    )
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("project", "name")
        ordering = ["project__name", "name"]

    def __str__(self):
        return f"{self.project.name} / {self.name}"


class LeadSubStatus(TimeStamped):
    """
    Sub-status under a status (infinite depth not required here; 1 level is enough,
    but you can make it recursive like classifications if you want).
    """
    status = models.ForeignKey(
        "LeadStatus",
        on_delete=models.CASCADE,
        related_name="sub_statuses",
    )
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("status", "name")
        ordering = ["status__project__name", "status__name", "name"]

    def __str__(self):
        return f"{self.status.project.name} / {self.status.name} / {self.name}"


class LeadPurpose(TimeStamped):
    """
    Optional: reasons/intents for the enquiry (e.g., Investment, Self-Use, Corporate).
    Keep simple; make hierarchical by adding parent if needed.
    """
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="lead_purposes",
    )
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("project", "name")
        ordering = ["project__name", "name"]

    def __str__(self):
        return f"{self.project.name} / {self.name}"


class ProjectLead(TimeStamped):
    """
    One row per project; just the header/meta.
    Other sections live in OneToOne child tables.
    """
    project = models.OneToOneField(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="lead_setup",
    )
    project_description = models.TextField(blank=True)
    logo = models.ImageField(upload_to=project_lead_logo_upload_to, null=True, blank=True)

    class Meta:
        verbose_name = "Project Lead Setup"
        verbose_name_plural = "Project Lead Setup"

    def __str__(self):
        return f"{self.project.name} Lead Setup"


class VisitingHalf(NamedLookup):
    project_lead = models.ForeignKey(
        "ProjectLead",
        on_delete=models.CASCADE,
        related_name="visiting_half_options",
        null=True,
        blank=True,
    )


class FamilySize(NamedLookup):
    project_lead = models.ForeignKey(
        "ProjectLead",
        on_delete=models.CASCADE,
        related_name="family_size_options",
        null=True,
        blank=True,
    )


class ResidencyOwnerShip(NamedLookup):
    project_lead = models.ForeignKey(
        "ProjectLead",
        on_delete=models.CASCADE,
        related_name="residency_ownership_options",
        null=True,
        blank=True,
    )


class PossienDesigned(NamedLookup):
    project_lead = models.ForeignKey(
        "ProjectLead",
        on_delete=models.CASCADE,
        related_name="possession_designed_options",
        null=True,
        blank=True,
    )


class Occupation(NamedLookup):
    project_lead = models.ForeignKey(
        "ProjectLead",
        on_delete=models.CASCADE,
        related_name="occupation_options",
        null=True,
        blank=True,
    )


class Designation(NamedLookup):
    project_lead = models.ForeignKey(
        "ProjectLead",
        on_delete=models.CASCADE,
        related_name="designation_options",
        null=True,
        blank=True,
    )


class AvailabilityStrategy(models.TextChoices):
    ROUND_ROBIN = "ROUND_ROBIN", "Round Robin"
    LEAST_LOAD  = "LEAST_LOAD",  "Least Load"
    RANDOM      = "RANDOM",      "Random"


class NewLeadAssignmentRule(TimeStamped):
    project_lead = models.ForeignKey(
        ProjectLead, on_delete=models.CASCADE, related_name="assignment_rules"
    )

    project = models.ForeignKey(
        "clientsetup.Project", null=True, blank=True,
        on_delete=models.CASCADE, related_name="assignment_rules"
    )
    source = models.ForeignKey(
        LeadSource, null=True, blank=True,
        on_delete=models.CASCADE, related_name="assignment_rules"
    )

    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="lead_assignment_pools"
    )

    availability_strategy = models.CharField(
        max_length=20, choices=AvailabilityStrategy.choices,
        default=AvailabilityStrategy.ROUND_ROBIN
    )
    
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project_lead", "is_active"]),
            models.Index(fields=["project"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        scope_p = self.project_id and f"{self.project.name}" or "All Projects"
        scope_s = self.source_id and f"{self.source.name}" or "Any Source"
        return f"Rule[{self.availability_strategy}] {scope_p} / {scope_s}"

    def clean(self):
        if self.source_id and self.project_id and self.source.project_id != self.project_id:
            raise ValidationError("Rule.source must belong to the chosen project.")


class LeadBudgetOffer(TimeStamped):
    project_lead = models.OneToOneField(
        ProjectLead, on_delete=models.CASCADE, related_name="budget_offer"
    )

    currency   = models.CharField(max_length=8, choices=Currency.choices, default=Currency.INR)
    budget_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    # default offering types (multi)
    offering_types = models.ManyToManyField(
        "setup.OfferingType", blank=True, related_name="lead_budget_offers"
    )

    class Meta:
        verbose_name = "Lead Budget & Offering"
        verbose_name_plural = "Lead Budget & Offering"

    def __str__(self):
        return f"BudgetOffer[{self.project_lead.project.name}]"

    def clean(self):
        if self.budget_min and self.budget_max and self.budget_min > self.budget_max:
            raise ValidationError("budget_min cannot be greater than budget_max.")


class ProjectLeadSiteVisitSetting(TimeStamped):
    project_lead = models.OneToOneField(
        ProjectLead, on_delete=models.CASCADE, related_name="site_settings"
    )

    # Site-visit settings
    enable_scheduled_visits = models.BooleanField(default=True)
    default_followup_days   = models.PositiveSmallIntegerField(default=3)

    # Notifications: e.g. ["EMAIL","SMS","IN_APP"]
    notify_channels = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Project Lead Site Settings"
        verbose_name_plural = "Project Lead Site Settings"

    def __str__(self):
        return f"SiteSettings[{self.project_lead.project.name}]"


class ProjectLeadReporting(TimeStamped):
    project_lead = models.OneToOneField(
        ProjectLead, on_delete=models.CASCADE, related_name="reporting"
    )

    report_type   = models.CharField(max_length=16, choices=ReportType.choices, default=ReportType.SUMMARY)
    export_format = models.CharField(max_length=8,  choices=ExportFormat.choices, default=ExportFormat.CSV)
    frequency     = models.CharField(max_length=12, choices=Frequency.choices,   default=Frequency.WEEKLY)

    class Meta:
        verbose_name = "Project Lead Reporting"
        verbose_name_plural = "Project Lead Reporting"

    def __str__(self):
        return f"Reporting[{self.project_lead.project.name}]"


