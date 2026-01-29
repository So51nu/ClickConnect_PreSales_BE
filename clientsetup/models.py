# clientsetup/models.pyy
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from setup.models import (
    ProjectType, TowerType, UnitType, Facing, ParkingType, UnitConfiguration
)
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import RegexValidator
from decimal import Decimal
from django.db import models
from django.contrib.postgres.fields import ArrayField  # agar PG ho to yeh bhi option hai
from django.core.validators import MinValueValidator


User = settings.AUTH_USER_MODEL

class NotificationType(models.TextChoices):
    SYSTEM = "SYSTEM", "System"
    MANUAL = "MANUAL", "Manual"

class NotificationPriority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"

class DeliveryMethod(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    PUSH = "PUSH", "Push"
    IN_APP = "IN_APP", "In-app"

class ReadStatus(models.TextChoices):
    UNREAD = "UNREAD", "Unread"
    READ = "READ", "Read"

class RowStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class ProjectStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    APPROVAL_PENDING = "APPROVAL_PENDING", "Approval Pending"
    APPROVED = "APPROVED", "Approved"
    UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION", "Under Construction"
    READY_TO_MOVE = "READY_TO_MOVE", "Ready to Move"
    ON_HOLD = "ON_HOLD", "On Hold"
    CANCELLED = "CANCELLED", "Cancelled"
    CLOSED = "CLOSED", "Closed"

class ApprovalStatus(models.TextChoices):
    NOT_REQUIRED = "NOT_REQUIRED", "Not Required"
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"
    REVOKED = "REVOKED", "Revoked"

class FloorStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    LOCKED = "LOCKED", "Locked"
    ARCHIVED = "ARCHIVED", "Archived"

class UnitStatus(models.TextChoices):
    NOT_RELEASED = "NOT_RELEASED", "Not Released"
    AVAILABLE = "AVAILABLE", "Available"
    HOLD = "HOLD", "Hold"
    BOOKED = "BOOKED", "Booked"
    SOLD = "SOLD", "Sold"
    CANCELLED = "CANCELLED", "Cancelled"
    BLOCKED = "BLOCKED", "Blocked"

class MilestonePlanStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    LOCKED = "LOCKED", "Locked"
    ARCHIVED = "ARCHIVED", "Archived"

class CalcMode(models.TextChoices):
    PERCENTAGE = "PERCENTAGE", "Percentage"
    AMOUNT = "AMOUNT", "Amount"

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Project(TimeStamped):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255, blank=True)
    developer = models.CharField(max_length=200, blank=True)
    rera_no = models.CharField(max_length=50, unique=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    at_lead_time_email=models.BooleanField(default=True)
    possession_date = models.DateField(null=True, blank=True)
    project_type = models.ForeignKey(ProjectType, on_delete=models.PROTECT, null=True, blank=True)
    office_address=models.CharField(max_length=100,null=True,blank=True)
    is_active = models.BooleanField(default=True)
    is_pricing_balcony_carpert=models.BooleanField(default=True)
    status = models.CharField(max_length=32, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT)
    approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
    notes = models.TextField(blank=True)
    reminder_offsets_minutes = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of reminder times in minutes before event date. "
            "Example: [1440, 60, 30] → 1 day, 1 hour, 30 minutes before."
        ),
    )


    price_per_sqft = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base price per square foot for this project"
    )
    price_per_parking = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base price per parking for this project"
    )
    belongs_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_projects",
        help_text="Owning ADMIN user",
    )

    class Meta:
        indexes = [models.Index(fields=["status"]), models.Index(fields=["approval_status"])]
        ordering = ["name"]

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Start date cannot be after end date.")
        if self.end_date and self.possession_date and self.end_date > self.possession_date:
            raise ValidationError("End date cannot be after possession date.")


    def get_reminder_offsets(self):
        """
        Safe helper: returns list[int] like [1440, 60, 30].
        Supports:
          - [] (no reminders)
          - [1440, 60]
          - ["1440", "60"]
        """
        raw = self.reminder_offsets_minutes or []
        cleaned = []
        for v in raw:
            try:
                iv = int(v)
                if iv > 0:
                    cleaned.append(iv)
            except (TypeError, ValueError):
                continue
        # sort largest -> smallest (just for consistency)
        cleaned.sort(reverse=True)
        return cleaned


    def __str__(self):
        return self.name

class Tower(TimeStamped):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="towers")
    name = models.CharField(max_length=100)
    tower_type = models.ForeignKey(TowerType, on_delete=models.PROTECT, null=True, blank=True)
    total_floors = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=FloorStatus.choices, default=FloorStatus.DRAFT)  # reuse simple lifecycle
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("project", "name")
        ordering = ["project__name", "name"]

    def __str__(self):
        return f"{self.project.name} - {self.name}"

class Floor(TimeStamped):
    tower = models.ForeignKey(Tower, on_delete=models.CASCADE, related_name="floors")
    number = models.CharField(max_length=20)  # allows "G", "1", "12A"
    total_units = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=FloorStatus.choices, default=FloorStatus.DRAFT)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("tower", "number")
        ordering = ["tower__name", "number"]

    def __str__(self):
        return f"{self.tower} / Floor {self.number}"

class FloorDocument(TimeStamped):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="floor_docs/")
    def __str__(self):
        return f"{self.floor} doc"

class Unit(TimeStamped):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="units")
    tower = models.ForeignKey(Tower, on_delete=models.PROTECT, related_name="units")
    floor = models.ForeignKey(Floor, on_delete=models.PROTECT, related_name="units")
    unit_no = models.CharField(max_length=50)
    unit_type = models.ForeignKey(UnitType, on_delete=models.PROTECT, null=True, blank=True)
    carpet_sqft = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    builtup_sqft = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rera_sqft = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    facing = models.ForeignKey(Facing, on_delete=models.PROTECT, null=True, blank=True)
    parking_type = models.ForeignKey(ParkingType, on_delete=models.PROTECT, null=True, blank=True)
    agreement_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    construction_start = models.DateField(null=True, blank=True)
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=UnitStatus.choices, default=UnitStatus.NOT_RELEASED)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("floor", "unit_no")
        indexes = [models.Index(fields=["project", "status"])]

    def __str__(self):
        return f"{self.tower.name}-{self.floor.number}-{self.unit_no}"


class MilestonePlan(TimeStamped):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestone_plans")
    tower = models.ForeignKey(Tower, on_delete=models.SET_NULL, null=True, blank=True, related_name="milestone_plans")
    name = models.CharField(max_length=150)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    responsible_user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="responsible_plans")
    calc_mode = models.CharField(max_length=12, choices=CalcMode.choices, default=CalcMode.PERCENTAGE)
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)  #
    enable_pg_integration = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_plans")
    verified_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=MilestonePlanStatus.choices, default=MilestonePlanStatus.DRAFT)
    
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("project", "name")
        ordering = ["project__name", "name"]


    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("Milestone start date cannot be after end date.")
        if self.status == MilestonePlanStatus.LOCKED and not (self.verified_by and self.verified_date):
            raise ValidationError("Locked plans must have Verified By and Verified Date.")
        # NEW validation for amount
        if self.calc_mode == CalcMode.AMOUNT and self.amount is None:
            raise ValidationError("Amount is required in amount mode.")
        if self.calc_mode == CalcMode.PERCENTAGE and self.amount:
            raise ValidationError("Do not set amount in percentage mode.")
        
    def __str__(self):
        scope = self.tower.name if self.tower_id else "All Towers"
        return f"{self.project.name} / {scope} / {self.name}"


class MilestoneSlab(TimeStamped):
    plan = models.ForeignKey(MilestonePlan, on_delete=models.CASCADE, related_name="slabs")
    order_index = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=120)
    percentage = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order_index"]
        unique_together = ("plan", "order_index")

    def clean(self):
        if self.plan.calc_mode == CalcMode.PERCENTAGE and self.percentage is None:
            raise ValidationError("Percentage is required in percentage mode.")
        if self.plan.calc_mode == CalcMode.AMOUNT and self.amount is None:
            raise ValidationError("Amount is required in amount mode.")
        if self.plan.calc_mode == CalcMode.PERCENTAGE and self.amount:
            raise ValidationError("Do not set amount in percentage mode.")
        if self.plan.calc_mode == CalcMode.AMOUNT and self.percentage:
            raise ValidationError("Do not set percentage in amount mode.")

    def __str__(self):
        return f"{self.plan} / {self.order_index}. {self.name}"


class PaymentPlan(TimeStamped):
    """
    Simple percentage-only plan tied to a Project.
    Ye sirf MASTER / project-level plans hain.
    Custom booking plans is table me create nahi honge.
    """
    code = models.CharField(
        max_length=30,
        unique=True,
        help_text="e.g., PPL001",
    )
    name = models.CharField(max_length=150)

    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="payment_plans",
    )

    class Meta:
        unique_together = ("project", "name")
        ordering = ["project__name", "name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    @property
    def total_percentage(self) -> float:
        return float(self.slabs.aggregate(s=models.Sum("percentage"))["s"] or 0.0)


class PaymentSlab(TimeStamped):
    """
    Plan ke andar ek-ek slab.
    Screenshot wale 'Name / Percentage / Days' se map hota hai.
    """
    plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.CASCADE,
        related_name="slabs",
    )
    order_index = models.PositiveIntegerField(default=1)
    name = models.CharField(max_length=120)
    percentage = models.DecimalField(max_digits=6, decimal_places=3)
    days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Days from booking/agreement etc.",
    )

    class Meta:
        unique_together = ("plan", "order_index")
        ordering = ["order_index"]

    def __str__(self) -> str:
        return f"{self.plan.code} - {self.order_index}. {self.name}"

    def clean(self):
        from django.db.models import Sum

        siblings_sum = (
            PaymentSlab.objects
            .filter(plan=self.plan)
            .exclude(pk=self.pk)
            .aggregate(s=Sum("percentage"))["s"]
            or 0
        )
        if siblings_sum + (self.percentage or 0) > 100:
            raise ValidationError("Total percentage for a plan cannot exceed 100.")


class Bank(TimeStamped):
    code = models.CharField(max_length=20, unique=True)  # BNK001
    name = models.CharField(max_length=150)
    bank_type = models.ForeignKey("setup.BankType", on_delete=models.PROTECT)
    bank_category = models.ForeignKey("setup.BankCategory", on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.code} - {self.name}"


IFSC_VALIDATOR = RegexValidator(
    r"^[A-Z]{4}0[0-9A-Z]{6}$",
    "Invalid IFSC format. Expected like HDFC0001234"
)

class BankBranch(TimeStamped):
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, related_name="branches")
    branch_name = models.CharField(max_length=150)
    branch_code = models.CharField(max_length=50, blank=True)
    ifsc = models.CharField(max_length=11, unique=True, validators=[IFSC_VALIDATOR])
    micr = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_phone = models.CharField(max_length=32, blank=True)
    contact_email = models.EmailField(blank=True)

    class Meta:
        unique_together = ("bank", "branch_name")

    def __str__(self):
        return f"{self.bank.code} / {self.branch_name}"


class ProjectBankStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class ProjectBank(TimeStamped):
    """Bank linkage for a specific Project (screenshot form)."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_banks")
    bank_branch = models.ForeignKey(BankBranch, on_delete=models.PROTECT, related_name="project_banks")
    apf_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=ProjectBankStatus.choices, default=ProjectBankStatus.ACTIVE)

    class Meta:
        unique_together = ("project", "bank_branch")

    def __str__(self):
        return f"{self.project.name} - {self.bank_branch}"


class ProjectBankProduct(TimeStamped):
    project_bank = models.ForeignKey(ProjectBank, on_delete=models.CASCADE, related_name="products")
    product = models.ForeignKey("setup.LoanProduct", on_delete=models.PROTECT)

    class Meta:
        unique_together = ("project_bank", "product")


class Notification(TimeStamped):
    code = models.CharField(max_length=30, unique=True)  # e.g., n1
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    notif_type = models.CharField(max_length=10, choices=NotificationType.choices, default=NotificationType.SYSTEM)
    message = models.TextField()
    priority = models.CharField(max_length=6, choices=NotificationPriority.choices, default=NotificationPriority.MEDIUM)
    delivery_method = models.CharField(max_length=10, choices=DeliveryMethod.choices, default=DeliveryMethod.EMAIL)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    read_status = models.CharField(max_length=6, choices=ReadStatus.choices, default=ReadStatus.UNREAD)
    status = models.CharField(max_length=8, choices=RowStatus.choices, default=RowStatus.ACTIVE)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")
    def __str__(self):
        return f"{self.code} -> {self.user} ({self.priority})"


class NotificationDispatchLog(TimeStamped):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="dispatch_logs")
    attempt_no = models.PositiveIntegerField(default=1)
    channel = models.CharField(max_length=10, choices=DeliveryMethod.choices)
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    response_meta = models.JSONField(blank=True, null=True)



def inventory_photo_upload_to(instance, filename):
    return f"inventory/{instance.id or 'new'}/photo/{filename}"

def inventory_doc_upload_to(instance, filename):
    return f"inventory/{instance.inventory_id or 'new'}/{instance.doc_type.lower()}/{filename}"


class InventoryStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class AvailabilityStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Available"
    BOOKED    = "BOOKED", "Booked"
    BLOCKED   = "BLOCKED", "Blocked"


class Inventory(TimeStamped):
    project = models.ForeignKey("Project", on_delete=models.CASCADE, related_name="inventories", null=True, blank=True)
    tower   = models.ForeignKey("Tower",   on_delete=models.SET_NULL, related_name="inventories", null=True, blank=True)
    floor   = models.ForeignKey("Floor",   on_delete=models.SET_NULL, related_name="inventories", null=True, blank=True)
    unit    = models.OneToOneField("Unit",    on_delete=models.SET_NULL, related_name="inventory_items", null=True, blank=True)

    unit_type     = models.ForeignKey(UnitType, on_delete=models.SET_NULL, null=True, blank=True)
    configuration = models.ForeignKey(UnitConfiguration, on_delete=models.SET_NULL, null=True, blank=True)
    facing        = models.ForeignKey(Facing, on_delete=models.SET_NULL, null=True, blank=True)

    carpet_sqft    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    builtup_sqft   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rera_area_sqft = models.DecimalField("RERA Area (sq.ft)", max_digits=10, decimal_places=2, null=True, blank=True)
    balcony_area_sqft = models.DecimalField(
        "Balcony Area (Sq.ft)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    saleable_sqft  = models.DecimalField("Saleable Area (Sq.ft)", max_digits=10, decimal_places=2, null=True, blank=True)
    other_area_sqft = models.DecimalField("Other Area (Sq.ft)", max_digits=10, decimal_places=2, null=True, blank=True)
    loft_area_sqft  = models.DecimalField("Loft Area (Sq.ft)", max_digits=10, decimal_places=2, null=True, blank=True)

    # Pricing
    core_base_price_psf = models.DecimalField(
        "Core Base Price (per sq.ft)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Original/base rate before any approvals or discounts"
    )
    approved_limit_price_psf = models.DecimalField(
        "Approved Limit Price (per sq.ft)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Lowest rate sales team is allowed to go till (management approved)"
    )
    customer_base_price_psf = models.DecimalField(
        "Customer Base Price (per sq.ft)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rate currently being offered/pitched to customer for this unit"
    )
    base_price_psf = models.DecimalField("Base Price (per sq.ft)", max_digits=12, decimal_places=2, null=True, blank=True)
    rate_psf       = models.DecimalField("Rate (per sq.ft)", max_digits=12, decimal_places=2, null=True, blank=True)

    agreement_value = models.DecimalField("Agreement Value", max_digits=14, decimal_places=2, null=True, blank=True)
    gst_amount      = models.DecimalField("GST Amount", max_digits=12, decimal_places=2, null=True, blank=True)

    # Charges / Costs
    development_infra_charge = models.DecimalField("Development/Infra Charge", max_digits=12, decimal_places=2, null=True, blank=True)
    stamp_duty_amount        = models.DecimalField("Stamp Duty Amount", max_digits=12, decimal_places=2, null=True, blank=True)
    registration_charges     = models.DecimalField("Registration Charges", max_digits=12, decimal_places=2, null=True, blank=True)
    legal_fee                = models.DecimalField("Legal Fee", max_digits=12, decimal_places=2, null=True, blank=True)
    total_cost               = models.DecimalField("Total Cost", max_digits=14, decimal_places=2, null=True, blank=True)

    unit_status  = models.CharField(max_length=16, choices=UnitStatus.choices, default=UnitStatus.NOT_RELEASED)
    status       = models.CharField(max_length=12, choices=InventoryStatus.choices, default=InventoryStatus.DRAFT)
    availability_status = models.CharField(
        "Inventory Availability",
        max_length=9,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
        help_text="Business-facing availability: Available / Booked / Blocked",
    )

    # Misc
    block_period_days   = models.PositiveIntegerField("Block Period (days)", null=True, blank=True)
    registration_number = models.CharField("Registration Number", max_length=64, blank=True)
    description         = models.TextField("Inventory Description", blank=True)
    photo               = models.ImageField(upload_to=inventory_photo_upload_to, null=True, blank=True)
    blocked_until = models.DateTimeField(
        null=True, blank=True,
        help_text="When block period ends. After this inventory becomes AVAILABLE again."
    )

    class Meta:
        indexes = [
            models.Index(fields=["project", "tower", "status"]),
            models.Index(fields=["unit_status"]),
            models.Index(fields=["availability_status"]),
        ]
        ordering = ["-id"]

    def compute_total_cost(self):
        """
        Base:
          - If agreement_value is provided, use it as base.
          - Else base = rate_psf * preferred_area
              Preferred area order: saleable_sqft -> rera_area_sqft -> carpet_sqft -> builtup_sqft
        Then add: development_infra_charge + gst_amount + stamp_duty_amount
                  + registration_charges + legal_fee
        """
        amount = Decimal("0.00")

        if self.agreement_value:
            amount += self.agreement_value
        else:
            area = (
                self.saleable_sqft
                or self.rera_area_sqft
                or self.carpet_sqft
                or self.builtup_sqft
            )
            if self.rate_psf and area:
                amount += (self.rate_psf * area)

        for x in [
            self.development_infra_charge,
            self.gst_amount,
            self.stamp_duty_amount,
            self.registration_charges,
            self.legal_fee,
        ]:
            if x:
                amount += x

        return amount if amount > 0 else None

    def save(self, *args, **kwargs):
        # existing auto-fill from unit (unchanged)
        if self.unit:
            if not self.project_id:
                self.project_id = self.unit.project_id
            if not self.tower_id:
                self.tower_id = self.unit.tower_id
            if not self.floor_id:
                self.floor_id = self.unit.floor_id
            if not self.unit_type_id:
                self.unit_type_id = self.unit.unit_type_id
            if not self.facing_id:
                self.facing_id = self.unit.facing_id
            if not self.carpet_sqft and self.unit.carpet_sqft:
                self.carpet_sqft = self.unit.carpet_sqft
            if not self.builtup_sqft and self.unit.builtup_sqft:
                self.builtup_sqft = self.unit.builtup_sqft

        # Auto-compute total_cost if not set
        if self.total_cost is None:
            try:
                computed = self.compute_total_cost()
                if computed is not None:
                    self.total_cost = computed
            except Exception:
                pass

        super().save(*args, **kwargs)

    def block(
        self,
        *,
        days: int | None = None,
        reason: str = "",
        changed_by=None,
        save: bool = True,
    ):
        """
        Business helper:
        - Marks this inventory as BLOCKED (availability)
        - Optionally updates unit_status (if currently free-like)
        - Computes blocked_until based on days / block_period_days
        - Writes an InventoryStatusHistory log row

        NOTE: This implementation DOES NOT change the DB schema.
        It writes availability changes to InventoryStatusHistory using the
        existing fields (`old_availability`, `new_availability`). If you want
        structured unit-status columns in history, add fields to the model
        and then run makemigrations/migrate.
        """
        from datetime import timedelta
        from django.utils import timezone

        # Snapshot old values for logging
        old_unit_status = self.unit_status
        old_availability = self.availability_status

        # Decide how long to block:
        # 1) explicit days argument wins
        # 2) fallback to self.block_period_days if set
        # 3) if nothing, we still block but don't set blocked_until
        if days is None:
            days = self.block_period_days

        blocked_until = None
        if days and days > 0:
            blocked_until = timezone.now() + timedelta(days=days)

        # Set availability to BLOCKED
        self.availability_status = AvailabilityStatus.BLOCKED

        # If unit is not already BOOKED / SOLD / CANCELLED,
        # we treat it as BLOCKED at unit-status level too.
        if self.unit_status in [
            UnitStatus.NOT_RELEASED,
            UnitStatus.AVAILABLE,
            UnitStatus.HOLD,
            UnitStatus.CANCELLED,
        ]:
            self.unit_status = UnitStatus.BLOCKED

        # Set blocked_until (may be None if no days)
        self.blocked_until = blocked_until

        if save:
            # Save only the fields we changed (best practice)
            try:
                self.save(update_fields=["availability_status", "unit_status", "blocked_until"])
            except Exception:
                # Fallback: try saving availability only
                self.save(update_fields=["availability_status"])

        # Compose a reason that also includes unit-status change for traceability
        history_reason = reason or "Inventory blocked"
        # Add unit status snapshot so humans can read it later (no DB change required)
        history_reason = f"{history_reason} (unit_status: {old_unit_status} -> {self.unit_status})"

        # Write history using existing model fields (no migrations)
        InventoryStatusHistory.objects.create(
            inventory=self,
            old_availability=old_availability,
            new_availability=self.availability_status,
            reason=history_reason,
            changed_by=changed_by,
        )

        return self



class InventoryStatusHistory(TimeStamped):
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name="status_history")
    old_availability = models.CharField(max_length=9, choices=AvailabilityStatus.choices)
    new_availability = models.CharField(max_length=9, choices=AvailabilityStatus.choices)
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)


class InventoryDocument(TimeStamped):
    FLOOR_PLAN   = "FLOOR_PLAN"
    OTHER        = "OTHER"
    PROJECT_PLAN = "PROJECT_PLAN"
    DOC_TYPES = [
        (FLOOR_PLAN,   "Floor Plan"),
        (OTHER,        "Other"),
        (PROJECT_PLAN, "Project Plan"),
    ]

    inventory     = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name="documents")
    doc_type      = models.CharField(max_length=20, choices=DOC_TYPES)
    file          = models.FileField(upload_to=inventory_doc_upload_to)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by   = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        indexes = [models.Index(fields=["inventory", "doc_type"])]

    def __str__(self):
        return f"Inv#{self.inventory_id} {self.doc_type}"




from django.conf import settings
from django.db import models


class OfferTargetType(models.TextChoices):
    CUSTOMER        = "CUSTOMER", "Customer"
    CHANNEL_PARTNER = "CHANNEL_PARTNER", "Channel Partner"


class OfferValueType(models.TextChoices):
    AMOUNT     = "AMOUNT", "Flat Amount"
    PERCENTAGE = "PERCENTAGE", "Percentage"
    GIFT       = "GIFT", "Gift / Non-monetary"



class CommercialOffer(TimeStamped):
    """
    Common Offer master:
      - For CUSTOMER or CP
      - Value can be Amount / % / Gift
      - Scoped by Admin, Project, CP Tier
    """

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="offers_created",
        help_text="Admin who owns this offer scheme",
    )

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    # WHO ke liye offer hai
    target_type = models.CharField(
        max_length=20,
        choices=OfferTargetType.choices,
        default=OfferTargetType.CUSTOMER,
    )

    # Scope
    project = models.ForeignKey(
        "clientsetup.Project",
        on_delete=models.CASCADE,
        related_name="offers",
        null=True,
        blank=True,
        help_text="Null = all projects of this admin",
    )
    cp_tier = models.ForeignKey(
        "channel.PartnerTier",
        on_delete=models.CASCADE,
        related_name="offers",
        null=True,
        blank=True,
        help_text="Required when target_type=CHANNEL_PARTNER",
    )

    # Value
    value_type = models.CharField(
        max_length=20,
        choices=OfferValueType.choices,
        default=OfferValueType.AMOUNT,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Flat amount discount / benefit",
    )
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage discount (e.g. 5.00 = 5%)",
    )
    gift_description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Eg. 'Free Car', 'Modular Kitchen', etc.",
    )

    # Conditions
    min_booking_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum agreement / deal value required (optional)",
    )

    valid_from = models.DateField(null=True, blank=True)
    valid_till = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["admin", "target_type", "is_active"]),
            models.Index(fields=["project"]),
            models.Index(fields=["valid_till"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_target_type_display()})"

    def clean(self):
        from django.core.exceptions import ValidationError

        # CP offers must have tier
        if self.target_type == OfferTargetType.CHANNEL_PARTNER and not self.cp_tier_id:
            raise ValidationError("cp_tier required when target_type=CHANNEL_PARTNER.")

        # Value-type validation
        if self.value_type == OfferValueType.AMOUNT:
            if self.amount is None:
                raise ValidationError("amount required for AMOUNT offers.")
            self.percentage = None

        elif self.value_type == OfferValueType.PERCENTAGE:
            if self.percentage is None:
                raise ValidationError("percentage required for PERCENTAGE offers.")
            self.amount = None

        elif self.value_type == OfferValueType.GIFT:
            if not self.gift_description:
                raise ValidationError("gift_description required for GIFT offers.")
            self.amount = None
            self.percentage = None





from django.utils import timezone

class ParkingType(models.TextChoices):
    OPEN    = "OPEN", "Open"
    COVERED = "COVERED", "Covered"
    STILT   = "STILT", "Stilt"
    PODIUM  = "PODIUM", "Podium"
    OTHER   = "OTHER", "Other"


class ParkingVehicleType(models.TextChoices):
    TWO_WHEELER   = "TWO_WHEELER", "Two wheeler"
    FOUR_WHEELER  = "FOUR_WHEELER", "Four wheeler"
    BOTH          = "BOTH", "Both"


class ParkingUsageType(models.TextChoices):
    RESIDENT   = "RESIDENT", "Resident"
    VISITOR    = "VISITOR", "Visitor"
    STAFF      = "STAFF", "Staff"
    COMMERCIAL = "COMMERCIAL", "Commercial"


class ParkingInventory(TimeStamped):
    """
    Per-project parking slot master.
    Booking ke time yahan se slot pick karke assign karoge.
    """

    # ---------- Scope / Relations ----------
    project = models.ForeignKey(
        "Project",
        on_delete=models.CASCADE,
        related_name="parking_inventories",
        help_text="Project to which this parking belongs",
    )
    tower = models.ForeignKey(
        "Tower",
        on_delete=models.SET_NULL,
        related_name="parking_inventories",
        null=True,
        blank=True,
        help_text="Optional – if parking tower-wise segregated hai",
    )
    floor = models.ForeignKey(
        "Floor",
        on_delete=models.SET_NULL,
        related_name="parking_inventories",
        null=True,
        blank=True,
        help_text="Optional – exact parking level (Basement-1 / Podium-2 etc.)",
    )

    # Agar specific flat ke saath tied hai:
    reserved_for_unit = models.ForeignKey(
        "Unit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reserved_parkings",
        help_text="If this slot is reserved for a particular unit / flat",
    )

    # ---------- Identity / Label ----------
    # e.g. "A53", "B1-12", "P2-45"
    slot_label = models.CharField(
        max_length=50,
        help_text="Full slot label as seen on paper (e.g. A53, B1-12, P2-45)",
    )

    # To support A53 style:
    block_label = models.CharField(
        max_length=20,
        blank=True,
        help_text="Block / Row / Zone label (e.g. A, B1, C-Wing)",
    )
    slot_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Running number within block (e.g. 53)",
    )

    parking_type = models.CharField(
        max_length=10,
        choices=ParkingType.choices,
        default=ParkingType.OPEN,
    )

    level_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Text label for level – Basement-1 / Podium-2 / Ground etc.",
    )

    # ---------- RERA / Regulatory ----------
    rera_slot_no = models.CharField(
        "RERA Slot No.",
        max_length=50,
        blank=True,
        help_text="Parking slot number as per RERA-approved plan",
    )
    rera_parking_type = models.CharField(
        "RERA Parking Type",
        max_length=50,
        blank=True,
        help_text="e.g. Covered / Open as per RERA, if different from internal type",
    )

    area_sqft = models.DecimalField(
        "Parking Area (sq.ft)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Approx. area of the parking slot (for documentation / costing)",
    )

    # ---------- Vehicle / Usage ----------
    vehicle_type = models.CharField(
        max_length=16,
        choices=ParkingVehicleType.choices,
        default=ParkingVehicleType.FOUR_WHEELER,
        help_text="Two wheeler / Four wheeler / Both",
    )
    usage_type = models.CharField(
        max_length=16,
        choices=ParkingUsageType.choices,
        default=ParkingUsageType.RESIDENT,
        help_text="Resident / Visitor / Staff / Commercial",
    )

    is_ev_ready = models.BooleanField(
        default=False,
        help_text="EV charging point available at this slot?",
    )
    is_accessible = models.BooleanField(
        default=False,
        help_text="Accessible / wider slot (specially-abled etc.)?",
    )

    # ---------- Status / Lifecycle ----------
    status = models.CharField(
        max_length=12,
        choices=InventoryStatus.choices,
        default=InventoryStatus.DRAFT,
        help_text="Parking master status (Draft/Active/Inactive)",
    )
    availability_status = models.CharField(
        max_length=9,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
        help_text="Available / Booked / Blocked",
    )

    blocked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When block period ends. After this slot can be made AVAILABLE again.",
    )

    remarks = models.TextField(blank=True)

    class Meta:
        unique_together = [("project", "slot_label")]
        indexes = [
            models.Index(fields=["project", "availability_status"]),
            models.Index(fields=["project", "vehicle_type", "usage_type"]),
        ]
        ordering = ["project_id", "slot_label"]

    def __str__(self):
        return f"{self.project} – Parking {self.slot_label}"

    # ---------- Label helper ----------
    def _autofill_slot_label(self):
        """
        Agar slot_label blank hai lekin block_label / slot_number diye hain,
        to automatically 'A53' ya 'A-53' bana sakte ho.
        """
        if self.slot_label:
            return

        if self.block_label and self.slot_number:
            # Decide format: "A53" vs "A-53"
            self.slot_label = f"{self.block_label}{self.slot_number}"
        else:
            self.slot_label = self.block_label or self.slot_number or ""

    # --- small helpers (like Inventory.block) ---
    def block(self, *, days: int | None = None, reason: str = "", changed_by=None, save: bool = True):
        from datetime import timedelta

        old_availability = self.availability_status

        blocked_until = None
        if days and days > 0:
            blocked_until = timezone.now() + timedelta(days=days)

        self.availability_status = AvailabilityStatus.BLOCKED
        self.blocked_until = blocked_until

        if save:
            self._autofill_slot_label()
            self.save()

        ParkingStatusHistory.objects.create(
            parking=self,
            old_availability=old_availability,
            new_availability=self.availability_status,
            reason=reason or "Parking blocked",
            changed_by=changed_by,
        )

        return self

    def mark_booked(self, *, reason: str = "", changed_by=None, save: bool = True):
        old_availability = self.availability_status
        self.availability_status = AvailabilityStatus.BOOKED
        self.blocked_until = None

        if save:
            self._autofill_slot_label()
            self.save()

        ParkingStatusHistory.objects.create(
            parking=self,
            old_availability=old_availability,
            new_availability=self.availability_status,
            reason=reason or "Parking booked",
            changed_by=changed_by,
        )

        return self

    def release(self, *, reason: str = "", changed_by=None, save: bool = True):
        """Cancel / unblock booking: make AVAILABLE again."""
        old_availability = self.availability_status
        self.availability_status = AvailabilityStatus.AVAILABLE
        self.blocked_until = None

        if save:
            self._autofill_slot_label()
            self.save()

        ParkingStatusHistory.objects.create(
            parking=self,
            old_availability=old_availability,
            new_availability=self.availability_status,
            reason=reason or "Parking released",
            changed_by=changed_by,
        )

        return self


class ParkingStatusHistory(TimeStamped):
    parking = models.ForeignKey(
        ParkingInventory,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_availability = models.CharField(
        max_length=9,
        choices=AvailabilityStatus.choices,
    )
    new_availability = models.CharField(
        max_length=9,
        choices=AvailabilityStatus.choices,
    )
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Parking#{self.parking_id}: {self.old_availability} → {self.new_availability}"
