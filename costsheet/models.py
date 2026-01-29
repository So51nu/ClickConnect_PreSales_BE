# costsheet/models.py
from django.utils.functional import cached_property
from django.db import models
from accounts.models import User       
from clientsetup.models import Project
from django.conf import settings
from decimal import Decimal
from common.utils import get_project_code

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CostSheetTemplate(TimeStamped):
    """
    Master Cost Sheet Template
    - Created by Admin
    - Company, logo, header, taxes, fees, T&C
    """

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cost_sheet_templates_created",
    )

    company_name = models.CharField(max_length=255)
    company_logo = models.ImageField(
        upload_to="costsheet/logos/", blank=True, null=True
    )

    quotation_header = models.CharField(
        max_length=255,
        help_text="Heading shown on Cost Sheet.",
    )
    quotation_subheader = models.CharField(max_length=255, blank=True)

    # 🔹 Validity (max days)
    validity_days = models.PositiveIntegerField(default=7)

    # 🔹 Taxes / Charges
    gst_percent = models.DecimalField(          # % of basic/total
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="GST percentage (e.g. 5.00, 18.00)",
    )
    is_plan_required = models.BooleanField(
        default=True,
        help_text="If false, payment plan selection is optional for this template.",
    )
    stamp_duty_percent = models.DecimalField(   # still percent
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Stamp duty percentage.",
    )



    # 👉 Registration now as amount (NOT percent)
    registration_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Registration fee amount (absolute value).",
    )

    share_application_money_membership_fees = models.DecimalField(          # % of basic/total
        max_digits=5,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        help_text="money_membership",
    )
    development_charges_psf= models.DecimalField(  
        max_digits=5,
        decimal_places=2,
        default=0,
                null=True,
        blank=True,
        help_text="Development Charges in Amount per Square Feet.",
    )
    electrical_watern_n_all_charges=models.DecimalField(          # % of basic/total
        max_digits=7,
        decimal_places=2,
        default=0,
                null=True,
        blank=True,
        help_text="psf",
    )
    provisional_maintenance_psf=models.DecimalField(          # % of basic/total
        max_digits=5,
        decimal_places=2,
        default=0,
        null=True,
        blank=True,
        help_text="psf",
    )
    provisional_maintenance_months = models.PositiveIntegerField(
        default=6,
        null=True,
        blank=True,
        help_text="Number of months for provisional maintenance (e.g. 6).",
    )

    # 👉 Legal fees as amount
    legal_fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Legal fees amount.",
    )
    # 👉 Possessional charges toggle + GST %
    is_possessional_charges = models.BooleanField(
        default=False,
        help_text="If true, template includes possessional charges.",
    )

    possessional_gst_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="GST percentage specifically on possessional charges.",
    )

    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Default T&C for this cost sheet template.",
    )

    config = models.JSONField(
        blank=True,
        null=True,
        help_text="Any extra JSON config: sections, extra charges schema, etc.",
    )

    def __str__(self):
        return f"Cost Sheet Template #{self.id} - {self.company_name}"






class ProjectCostSheetTemplate(TimeStamped):
    """
    Mapping between Project and CostSheetTemplate
    - No branding / header / tax / fees here
    - Sirf yeh batata hai: is project me kaunsa template use hoga
    """

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="project_cost_sheet_templates_created",
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="project_cost_sheet_templates",
    )

    template = models.ForeignKey(
        CostSheetTemplate,
        on_delete=models.CASCADE,
        related_name="project_mappings",
    )

    is_active = models.BooleanField(default=True)

    extra_charges = models.JSONField(
        blank=True,
        null=True,
        help_text="Project specific extra charges config if any.",
    )

    class Meta:
        unique_together = ("project", "template")

    def __str__(self):
        return f"{self.project.name} -> Template {self.template_id}"


    def clean(self):
        from django.core.exceptions import ValidationError

        # Auto-set project if missing
        if not self.project_id:
            if self.lead_id and self.lead.project_id:
                self.project_id = self.lead.project_id
            elif self.inventory_id and self.inventory.project_id:
                self.project_id = self.inventory.project_id

        # -------- Payment plan requirement logic --------
        # Default: plan is required
        is_plan_required = True

        # If project_template → template has is_plan_required, use that
        if self.project_template_id:
            tmpl = getattr(self.project_template, "template", None)
            if tmpl is not None and hasattr(tmpl, "is_plan_required"):
                is_plan_required = tmpl.is_plan_required

        if (
            self.payment_plan_type == CostSheetPaymentPlanType.MASTER
            and is_plan_required
            and not self.payment_plan_id
        ):
            raise ValidationError(
                "payment_plan required when payment_plan_type=MASTER and plan is required."
            )

        if (
            self.payment_plan_type == CostSheetPaymentPlanType.CUSTOM
            and not self.custom_payment_plan
        ):
            raise ValidationError(
                "custom_payment_plan required when payment_plan_type=CUSTOM."
            )



def costsheet_attachment_upload_to(instance, filename):
    return f"costsheet/{instance.costsheet_id or 'new'}/attachments/{filename}"



class CostSheetStatus(models.TextChoices):
    DRAFT    = "DRAFT", "Draft"
    SENT     = "SENT", "Sent to Customer"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    EXPIRED  = "EXPIRED", "Expired"



class CostSheetPaymentPlanType(models.TextChoices):
    MASTER = "MASTER", "Project Plan"
    CUSTOM = "CUSTOM", "Make Your Own"



class CostSheet(TimeStamped):
    """
    Quotation / Cost Sheet generated for a SalesLead.
    Snapshot that you share with customer.
    """

    # ---------------- Core links ----------------
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="cost_sheets",
    )

    lead = models.ForeignKey(
        "salelead.SalesLead",
        on_delete=models.CASCADE,
        related_name="cost_sheets",
    )

    # ⚠️ unit removed – we derive it from inventory.unit
    inventory = models.ForeignKey(
        "clientsetup.Inventory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_sheets",
        help_text="Inventory snapshot used for this quotation",
    )

    # ⚠️ template removed – use only project_template
    project_template = models.ForeignKey(
        "costsheet.ProjectCostSheetTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_cost_sheets",
        help_text="Project → CostSheetTemplate mapping used for this quotation.",
    )


    # ---------------- Parking / Statutory Charges ----------------
    parking_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of parking slots."
    )
    per_parking_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price per parking slot."
    )
    parking_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total parking amount = parking_count × per_parking_price."
    )

    share_application_money_membership_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Share Application Money & Membership Fees amount."
    )
    legal_compliance_charges_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Legal & Compliance Charges amount."
    )
    development_charges_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Development Charges amount."
    )
    electrical_water_piped_gas_charges_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Electrical, Water & Piped Gas Connection Charges amount."
    )
    provisional_maintenance_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Provisional Maintenance for 6 months amount."
    )

    possessional_gst_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="GST amount on possessional charges."
    )


    quotation_no = models.CharField(
        max_length=50,
        unique=True,
        help_text="External quotation / cost sheet number",
       null=True,
        blank=True,
    )

    date = models.DateField(help_text="Quotation date")
    valid_till = models.DateField()

    status = models.CharField(
        max_length=16,
        choices=CostSheetStatus.choices,
        default=CostSheetStatus.DRAFT,
    )

    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_sheets_prepared",
    )

    # ---------------- Customer + Unit section (snapshot) ----------------
    customer_name = models.CharField(max_length=255)
    customer_contact_person = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=32, blank=True)
    customer_email = models.EmailField(blank=True)

    project_name = models.CharField(max_length=255)
    tower_name = models.CharField(max_length=255, blank=True)
    floor_number = models.CharField(max_length=50, blank=True)
    unit_no = models.CharField(max_length=50, blank=True)

    customer_snapshot = models.JSONField(blank=True, null=True)
    unit_snapshot = models.JSONField(blank=True, null=True)

    # ---------------- Base Pricing section ----------------
    base_area_sqft = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Area considered for base rate (sq.ft)",
    )
    base_rate_psf = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base rate per sq.ft (from Project / Inventory)",
    )
    base_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="base_area_sqft × base_rate_psf",
    )

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Discount % on base value",
    )
    discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Discount amount in ₹",
    )

    net_base_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base value after discount",
    )

    # ---------------- Payment Plan section ----------------
    payment_plan_type = models.CharField(
        max_length=12,
        choices=CostSheetPaymentPlanType.choices,
        default=CostSheetPaymentPlanType.MASTER,
        null=True,
        blank=True,
    )
    payment_plan = models.ForeignKey(
        "clientsetup.PaymentPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quoted_cost_sheets",
        help_text="Used when payment_plan_type=MASTER",
    )
    custom_payment_plan = models.JSONField(
        null=True,
        blank=True,
        help_text="Used when payment_plan_type=CUSTOM; full slab structure",
    )

    # ---------------- Taxes (snapshot – from template / project settings) ----------------
    gst_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    gst_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    stamp_duty_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    stamp_duty_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    registration_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    legal_fee_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # ---------------- Totals ----------------
    additional_charges_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    offers_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total benefit from offers",
    )
    net_payable_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final figure shown to customer",
    )

    # ---------------- Texts ----------------
    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Default from CostSheetTemplate / project template",
    )
    notes = models.TextField(
        blank=True,
        help_text="Any extra notes per quotation",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["lead"]),
            models.Index(fields=["date", "valid_till"]),
        ]

    def __str__(self) -> str:
        return f"CostSheet {self.quotation_no} – {self.customer_name}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not self.project_id:
            if self.lead_id and self.lead.project_id:
                self.project_id = self.lead.project_id
            elif self.inventory_id and self.inventory.project_id:
                self.project_id = self.inventory.project_id

        if self.payment_plan_type == CostSheetPaymentPlanType.MASTER and not self.payment_plan_id:
            raise ValidationError("payment_plan required when payment_plan_type=MASTER.")
        if self.payment_plan_type == CostSheetPaymentPlanType.CUSTOM and not self.custom_payment_plan:
            raise ValidationError("custom_payment_plan required when payment_plan_type=CUSTOM.")


    @property
    def status_label(self) -> str:
        """
        Human-readable label for quotation status.
        e.g. DRAFT -> "Draft"
        """
        return self.get_status_display()

    @cached_property
    def quotation_attachment(self):
        """
        Primary PDF for the quotation.
        We assume CostSheetAttachment.doc_type="QUOTATION_PDF" for main file.
        """
        return (
            self.attachments
            .filter(doc_type="QUOTATION_PDF")
            .order_by("-created_at")
            .first()
        )


    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new and not self.quotation_no:
            project_code = get_project_code(self.project or self.lead.project)
            # Example: QTN-DS-000123
            qno = f"QTN-{project_code}-{self.pk:06d}"

            CostSheet.objects.filter(pk=self.pk).update(quotation_no=qno)
            self.quotation_no = qno


    @property
    def quotation_pdf_url(self) -> str | None:
        att = self.quotation_attachment
        if att and att.file:
            return att.file.url
        return None


class CostSheetAdditionalCharge(TimeStamped):
    costsheet = models.ForeignKey(
        "costsheet.CostSheet",
        on_delete=models.CASCADE,
        related_name="additional_charges",
    )
    name = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=1)
    is_taxable = models.BooleanField(
        default=True,
        help_text="Part of taxable value or not.",
    )

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.amount})"



class CostSheetAppliedOffer(TimeStamped):
    costsheet = models.ForeignKey(
        "costsheet.CostSheet",
        on_delete=models.CASCADE,
        related_name="applied_offers",
    )
    offer = models.ForeignKey(
        "clientsetup.CommercialOffer",
        on_delete=models.PROTECT,
        related_name="applied_on_costsheets",
    )
    applied_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final discount / benefit applied from this offer",
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("costsheet", "offer")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.offer.name} on {self.costsheet.quotation_no}"



class CostSheetAttachment(TimeStamped):
    costsheet = models.ForeignKey(
        "costsheet.CostSheet",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    label = models.CharField(max_length=150, blank=True)
    file = models.FileField(upload_to=costsheet_attachment_upload_to)
    doc_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional code: QUOTATION_PDF / SIGNED_COPY / OTHER",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.label or f"Attachment #{self.pk}"

