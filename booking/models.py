# booking/models
from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.db import models
from setup.models import TimeStamped
from clientsetup.models import PaymentPlan,PaymentSlab
from django.conf import settings
from clientsetup.models import Project,Unit
import secrets 
from django.utils.functional import cached_property
from clientsetup.models import ParkingInventory
from common.utils import get_project_code

class BookingStatus(models.TextChoices):
    DRAFT     = "DRAFT", "Draft"
    BLOCKED   = "BLOCKED", "Blocked"
    BOOKED    = "BOOKED", "Booked"
    CANCELLED = "CANCELLED", "Cancelled"


class KycStatus(models.TextChoices):
    PENDING   = "PENDING", "Pending"
    APPROVED  = "APPROVED", "Approved"
    REJECTED  = "REJECTED", "Rejected"


class PaymentPlanType(models.TextChoices):
    MASTER = "MASTER", "Project Plan"
    CUSTOM = "CUSTOM", "Custom (per booking)"


class Booking(TimeStamped):
    """
    Ek flat (Unit) ki booking / blocking.
    - Flat selection: project/tower/floor/unit
    - Lead + Channel Partner link
    - Payment plan: PaymentPlan FK ya custom JSON plan
    - Money: agreement value + advance
    - KYC + booking lifecycle status
    """

    # ---------- Links / FKs ----------
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    tower = models.ForeignKey(
        "clientsetup.Tower",
        on_delete=models.PROTECT,
        related_name="bookings",
        null=True,
        blank=True,
    )
    floor = models.ForeignKey(
        "clientsetup.Floor",
        on_delete=models.PROTECT,
        related_name="bookings",
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        "clientsetup.Unit",
        on_delete=models.PROTECT,
        related_name="bookings",
        help_text="Flat / Unit being booked or blocked",
    )
    customer_base_price_psf = models.DecimalField(
        "Customer Base Price (per sq.ft)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Negotiated base rate per sq.ft at the time of booking",
    )
    parking_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of parking slots allotted in this booking",
    )
    parking_total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Total amount for all allotted parking slots",
    )

    parking_slots = models.ManyToManyField(
        ParkingInventory,
        through="BookingParkingAllocation",
        related_name="bookings",
        blank=True,
        help_text="Parking slots allocated for this booking",
    )

    share_application_money_membership_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Share Application Money & Membership Fees amount.",
    )
    legal_compliance_charges_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Legal & Compliance Charges amount.",
    )


    development_charges_psf = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Development Charges rate per sq.ft (snapshot).",
    )

    discount_amount = models.DecimalField(
    max_digits=14,
    decimal_places=2,
    default=0,
    help_text="Total discount amount applied on this deal.",
    )


    gst_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="GST percentage applied (e.g. 5.00 or 18.00).",
    )

    stamp_duty_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Stamp duty percentage used for this booking.",
    )

    provisional_maintenance_months = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of months considered for provisional maintenance.",
    )


    development_charges_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Development Charges amount.",
    )
    signed_booking_file = models.FileField(
        upload_to="booking_signed_forms/",
        null=True,
        blank=True,
        help_text="Scanned signed booking form (PDF/image).",
    )
    electrical_water_piped_gas_charges_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Electrical, Water & Piped Gas Connection Charges amount.",
    )
    provisional_maintenance_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Provisional Maintenance amount.",
    )
    possessional_gst_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="GST amount on possessional charges.",
    )

    # Lead link (optional)
    sales_lead = models.ForeignKey(
        "salelead.SalesLead",
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
        help_text="Source SalesLead, if any",
    )

    # Snapshot of Channel Partner at time of booking (optional)
    channel_partner = models.ForeignKey(
        "accounts.User",  # adjust app-label if different
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bookings_created",
        null=True,
        blank=True,
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bookings_confirmed",
        null=True,
        blank=True,
        help_text="User who confirmed (BOOKED) this booking",
    )

    # ---------- Top bar info ----------
    form_ref_no = models.CharField(
        max_length=50,
        unique=True,
        null=True,
 blank=True,
        help_text="External form reference / booking form number",
    )
    booking_date = models.DateField()
    office_address = models.TextField(blank=True)

    # ---------- Primary applicant snapshot ----------
    primary_title = models.CharField(
        max_length=10,
        blank=True,
        help_text="Mr / Ms / Mrs / Dr, etc.",
    )
    primary_full_name = models.CharField(max_length=200)
    primary_email = models.EmailField(blank=True)
    primary_mobile_number = models.CharField(max_length=32, blank=True)

    # Extra contact fields
    email_2 = models.EmailField(blank=True)
    phone_2 = models.CharField(max_length=32, blank=True)

    # ---------- Address & profile ----------
    permanent_address = models.TextField(blank=True)
    correspondence_address = models.TextField(blank=True)

    PREFERRED_ADDRESS_CHOICES = (
        ("PERMANENT", "Permanent Address"),
        ("CORRESPONDENCE", "Correspondence Address"),
    )
    preferred_correspondence = models.CharField(
        max_length=16,
        choices=PREFERRED_ADDRESS_CHOICES,
        default="PERMANENT",
    )

    residential_status = models.CharField(
        max_length=32,
        blank=True,
        help_text="Owned / Rented / Company Provided, etc.",
    )

    # ---------- Flat info snapshot ----------
    super_builtup_sqft = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    carpet_sqft = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    balcony_sqft = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    agreement_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Final agreement value for this booking (snapshot)",
    )
    agreement_value_words = models.CharField(
        max_length=500,
        blank=True,
        help_text="Agreement value in words, for printing",
    )
    agreement_done = models.BooleanField(default=False)

    parking_required = models.BooleanField(default=False)
    parking_details = models.CharField(max_length=255, blank=True)
    parking_number = models.CharField(max_length=50, blank=True)

    # ---------- Tax ----------
    gst_no = models.CharField(max_length=20, blank=True)

    # ---------- KYC summary ----------
    kyc_status = models.CharField(
        max_length=12,
        choices=KycStatus.choices,
        default=KycStatus.PENDING,
    )
    kyc_deal_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Deal amount sent to client for KYC approval."
    )
    kyc_submitted_at = models.DateTimeField(null=True, blank=True)
    kyc_approved_at = models.DateTimeField(null=True, blank=True)
    kyc_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bookings_kyc_approved",
        null=True,
        blank=True,
    )

    # ---------- Payment Plan ----------
    payment_plan_type = models.CharField(
        max_length=12,
        choices=PaymentPlanType.choices,
        default=PaymentPlanType.MASTER,
    )

    # MASTER: FK to project PaymentPlan
    payment_plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.SET_NULL,
        related_name="bookings",
        null=True,
        blank=True,
        help_text="Only when payment_plan_type=MASTER",
    )

    # CUSTOM: per booking plan JSON
    # structure:
    # {
    #   "name": "Custom Plan Name",
    #   "slabs": [
    #       {"order": 1, "name": "On Booking", "percentage": 10.0, "days": 0},
    #       ...
    #   ]
    # }
    custom_payment_plan = models.JSONField(
        null=True,
        blank=True,
        help_text="Custom plan only for this booking (shown in 'Make Your Own')",
    )

    # ---------- Source of funding ----------
    loan_required = models.BooleanField(default=False)
    loan_bank_name = models.CharField(max_length=150, blank=True)
    loan_amount_expected = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )

    # ---------- Advance / Money ----------
    booking_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Booking amount taken now",
    )
    other_charges = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Any other charges collected as advance",
    )
    total_advance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="booking_amount + other_charges",
    )

    # ---------- Booking lifecycle ----------
    status = models.CharField(
        max_length=16,
        choices=BookingStatus.choices,
        default=BookingStatus.DRAFT,
    )
    blocked_at = models.DateTimeField(null=True, blank=True)
    booked_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_reason = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["unit"]),
            models.Index(fields=["sales_lead"]),
        ]

    def __str__(self) -> str:
        return f"Booking {self.form_ref_no} / {self.unit}"

    # ---- helpers ----
    def sync_from_unit(self):
        """
        Unit select hone ke baad project/tower/floor auto sync.
        """
        if self.unit_id:
            self.project = self.unit.project
            self.tower = self.unit.tower
            self.floor = self.unit.floor

    def clean(self):
        # Unit se project/tower/floor sync
        if self.unit_id:
            self.sync_from_unit()

        # Payment plan validations
        if self.payment_plan_type == PaymentPlanType.MASTER:
            if not self.payment_plan_id:
                raise ValidationError("payment_plan required when payment_plan_type=MASTER.")
            # MASTER case me custom JSON clear kar do (safety)
            self.custom_payment_plan = None

        if self.payment_plan_type == PaymentPlanType.CUSTOM:
            if not self.custom_payment_plan:
                raise ValidationError("custom_payment_plan required when payment_plan_type=CUSTOM.")

            slabs = (self.custom_payment_plan or {}).get("slabs") or []
            total_pct = sum(Decimal(str(s.get("percentage", 0))) for s in slabs)

            if total_pct != Decimal("100"):
                raise ValidationError("Custom payment plan slabs must total 100%.")

            # CUSTOM case me FK clear
            self.payment_plan = None

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        super().save(*args, **kwargs)

        if is_new and not self.form_ref_no:
            project_code = get_project_code(self.project)
            ref = f"BKG-{project_code}-{self.pk:06d}"

            Booking.objects.filter(pk=self.pk).update(form_ref_no=ref)
            self.form_ref_no = ref





    @property
    def status_label(self) -> str:
        """
        Human-readable label for status.
        DRAFT  -> "Draft"
        BOOKED -> "Booked"
        """
        return self.get_status_display()

    @cached_property
    def booking_form_attachment(self):
        """
        Try to pick the main booking PDF if attached.
        Prefer a specific doc_type if you decide one.
        """
        # Apni coding-style ke hisaab se doc_type set karo:
        # e.g. "BOOKING_FORM_PDF" ya "AGREEMENT_PDF"
        return (
            self.attachments
            .filter(doc_type__in=["BOOKING_FORM_PDF", "AGREEMENT_PDF"])
            .order_by("-created_at")
            .first()
        )

    @property
    def booking_form_pdf_url(self) -> str | None:
        att = self.booking_form_attachment
        if att and att.file:
            return att.file.url
        return None

# ------------------------------------------------------------
# Applicants (primary + co-applicants)
# ------------------------------------------------------------

class BookingApplicant(TimeStamped):
    """
    Har applicant (primary + additional) ke liye separate row.
    First Applicant = is_primary=True, sequence=1.
    Second/Third/Fourth + Spouse/Child sab yahin stored.
    """

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="applicants",
    )

    is_primary = models.BooleanField(default=False)
    sequence = models.PositiveSmallIntegerField(
        default=1,
        help_text="1 = First Applicant, 2 = Second, etc.",
    )

    title = models.CharField(max_length=10, blank=True)  # Mr/Ms/Mrs/Dr
    full_name = models.CharField(max_length=200)

    relation = models.CharField(
        max_length=50,
        blank=True,
        help_text="For co-applicants: Spouse / Child / Father etc.",
    )

    date_of_birth = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    mobile_number = models.CharField(max_length=32, blank=True)

    pan_no = models.CharField(max_length=32, blank=True)
    aadhar_no = models.CharField(max_length=32, blank=True)

    # Docs (front/back)
    pan_front = models.FileField(
        upload_to="booking_docs/pan/front/",
        null=True,
        blank=True,
    )
    pan_back = models.FileField(
        upload_to="booking_docs/pan/back/",
        null=True,
        blank=True,
    )
    aadhar_front = models.FileField(
        upload_to="booking_docs/aadhar/front/",
        null=True,
        blank=True,
    )
    aadhar_back = models.FileField(
        upload_to="booking_docs/aadhar/back/",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["booking", "sequence"]

    def __str__(self) -> str:
        label = "Primary" if self.is_primary else "Co-applicant"
        return f"{self.full_name} ({label})"


class BookingAttachment(TimeStamped):
    """
    Generic multi-attachment:
    - Agreement copy
    - Cheque/RTGS screenshot
    - Extra docs etc.
    """

    class DocType(models.TextChoices):
        AGREEMENT_PDF = "AGREEMENT_PDF", "Agreement PDF"
        BOOKING_FORM_PDF = "BOOKING_FORM_PDF", "Booking Form PDF"
        PAYMENT_PROOF = "PAYMENT_PROOF", "Payment Proof"
        IDENTITY_PROOF = "IDENTITY_PROOF", "Identity Proof"   
        OTHER = "OTHER", "Other"

    class PaymentMode(models.TextChoices):
        CHEQUE = "CHEQUE", "Cheque"
        RTGS = "RTGS", "RTGS / NEFT"
        UPI = "UPI", "UPI"
        CASH = "CASH", "Cash"
        OTHER = "OTHER", "Other"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    label = models.CharField(
        max_length=150,
        blank=True,
        help_text="Friendly name: e.g. 'Agreement PDF', 'Cheque scan'",
    )

    file = models.FileField(upload_to="booking_attachments/")

    # -------- Base type (kya document hai?) --------
    doc_type = models.CharField(
        max_length=50,
        blank=True,
        choices=DocType.choices,
        help_text="AGREEMENT_PDF / BOOKING_FORM_PDF / PAYMENT_PROOF / OTHER",
    )

    # -------- Optional payment meta (cheque etc.) --------
    payment_mode = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=PaymentMode.choices,
        help_text="Fill only for PAYMENT_PROOF – Cheque / RTGS / UPI / Cash / Other",
    )
    payment_ref_no = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cheque no / transaction id / UPI ref, etc.",
    )
    bank_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Bank name for cheque / RTGS payments",
    )
    payment_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount of this particular payment (optional but recommended).",
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of cheque / transaction.",
    )
    remarks = models.TextField(
        blank=True,
        help_text="Any extra notes – e.g. cheque return, re-deposited, etc.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        base = self.label or f"Attachment #{self.pk}"
        if self.doc_type == self.DocType.PAYMENT_PROOF:
            return f"{base} (Payment Proof)"
        return base

    @property
    def is_payment_proof(self) -> bool:
        return self.doc_type == self.DocType.PAYMENT_PROOF



class BookingKycRequest(models.Model):
    """
    Pre-booking KYC approval:
    - unit + project + proposed deal amount
    - created by sales user
    - approved/rejected by project admin
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="kyc_requests",
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        related_name="kyc_requests",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # sales / booking exec
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kyc_requests_created",
    )

    # jis admin ne approve/reject kiya
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kyc_requests_decided",
    )

    booking = models.OneToOneField(
        "booking.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kyc_request",
    )
    
    # amount proposed for this deal
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    # copy of important info to show approver safely
    snapshot = models.JSONField(default=dict, blank=True)
    # e.g. {
    #   "project_name": "...",
    #   "tower_name": "...",
    #   "floor_number": "5",
    #   "unit_no": "502",
    #   "carpet_sqft": "650",
    #   "agreement_value_suggested": "12000000.00"
    # }

    status = models.CharField(
        max_length=16,
        choices=KycStatus.choices,   # PENDING / APPROVED / REJECTED
        default=KycStatus.PENDING,
    )

    # optional remarks from approver
    decision_remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    # 🔐 one-time magic-link token
    one_time_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
    )
    token_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["unit", "status"]),
        ]

    def __str__(self):
        return f"KYCRequest #{self.pk} – {self.unit} – {self.status}"

    @classmethod
    def build_snapshot(cls, project, unit, *, agreement_value=None):
        return {
            "project_name": getattr(project, "name", ""),
            "tower_name": getattr(unit.tower, "name", "")
            if getattr(unit, "tower_id", None)
            else "",
            "floor_number": getattr(unit.floor, "number", "")
            if getattr(unit, "floor_id", None)
            else "",
            "unit_no": getattr(unit, "unit_no", ""),
            "carpet_sqft": str(getattr(unit, "carpet_sqft", "") or ""),
            "saleable_sqft": str(getattr(unit, "saleable_sqft", "") or ""),
            "agreement_value_suggested": str(agreement_value or ""),
        }

    # ---------- one-time link helpers ----------

    def generate_one_time_token(self, force: bool = False) -> str:
        """
        Call this before sending mail.
        Returns existing token unless `force=True`.
        """
        if self.one_time_token and not force:
            return self.one_time_token
        token = secrets.token_urlsafe(32)
        self.one_time_token = token
        self.token_used_at = None
        self.save(update_fields=["one_time_token", "token_used_at"])
        return token

    @property
    def is_link_used(self) -> bool:
        return self.token_used_at is not None



    # 🔹 yeh DO properties zaroori hain (AttributeError yahi se fix hoga)

    @property
    def paid_amount(self):
        """
        Total of all SUCCESS KYC payments linked to this KYC request.
        PaymentLead.for_kyc = True AND PaymentLead.kyc_request = self
        """
        from salelead.models import PaymentLead  # local import to avoid circular

        # 🔹 Agar instance save nahi hua (pk=None) -> koi payment logically nahi hoga
        if not self.pk:
            return Decimal("0.00")

        total = (
            PaymentLead.objects.filter(
                kyc_request_id=self.pk,  # ✅ id se filter, instance se nahi
                for_kyc=True,
                status=PaymentLead.PaymentStatus.SUCCESS,
            )
            .aggregate(total=Sum("amount"))
            .get("total")
        )
        if total is None:
            return Decimal("0.00")
        return total

    @property
    def is_fully_paid(self):
        """
        True if paid_amount >= required KYC amount.
        """
        if self.amount is None:
            return False
        return self.paid_amount >= self.amount


class BookingParkingAllocation(TimeStamped):
    """
    Join table: which parking slot is allocated to which booking.
    """

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="parking_allocations",
    )
    parking = models.ForeignKey(
        ParkingInventory,
        on_delete=models.PROTECT,
        related_name="allocations",
    )

    is_primary = models.BooleanField(
        default=True,
        help_text="In case of multiple slots, mark main slot"
    )
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("booking", "parking")]

    def __str__(self):
        return f"Booking#{self.booking_id} → Parking {self.parking.slot_label}"


# booking/models.py

class BookingStatusHistory(TimeStamped):
    """
    Audit log:
    - Kis booking ka status change hua
    - Old -> new status
    - Kisne change kiya
    - Kab kiya (created_at from TimeStamped)
    - Reason + action type (CREATE / CONFIRM / REJECT / AUTO_BLOCK / etc.)
    """

    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("CONFIRM", "Confirm"),
        ("REJECT", "Reject"),
        ("AUTO", "Auto Update"),
        ("MANUAL_UPDATE", "Manual Update"),
    ]

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    old_status = models.CharField(
        max_length=16,
        choices=BookingStatus.choices,
        blank=True,
    )
    new_status = models.CharField(
        max_length=16,
        choices=BookingStatus.choices,
    )

    # optional: KYC status bhi track karna ho to
    old_kyc_status = models.CharField(
        max_length=12,
        choices=KycStatus.choices,
        blank=True,
    )
    new_kyc_status = models.CharField(
        max_length=12,
        choices=KycStatus.choices,
        blank=True,
    )

    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES,
        default="MANUAL_UPDATE",
        help_text="What caused this change? e.g. CONFIRM / REJECT / CREATE",
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Reason given by user (if any).",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="booking_status_changes",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "new_status"]),
        ]

    def __str__(self):
        return f"Booking#{self.booking_id}: {self.old_status} → {self.new_status} ({self.action})"





class BookingAdditionalCharge(TimeStamped):
    """
    Extra line-item charges attached to a booking.
    Example:
      - "Club House Charges"
      - "Floor Rise"
      - "Infra Charges"
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="additional_charges",
    )
    label = models.CharField(
        max_length=255,
        help_text="Name of the charge (e.g. Club House, Floor Rise).",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text="Amount for this additional charge.",
    )

    class Meta:
        verbose_name = "Booking Additional Charge"
        verbose_name_plural = "Booking Additional Charges"

    def __str__(self) -> str:
        return f"{self.label} - {self.amount}"






