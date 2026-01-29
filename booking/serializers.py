
from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from clientsetup.models import (
    AvailabilityStatus,
    UnitStatus,          
    Project,
    Unit,
InventoryStatusHistory,
)
from .models import Booking, BookingAdditionalCharge, BookingParkingAllocation
from salelead.models import SalesLead
from accounts.models import ClientBrand
from django.utils import timezone
from .models import (
    Booking,
    BookingApplicant,
    BookingAttachment,
    PaymentPlan,
    BookingKycRequest,
    KycStatus,
    BookingStatus,
)
from clientsetup.models import ParkingInventory
from django.utils import timezone
from .models import (
    Booking,
    BookingApplicant,
    BookingParkingAllocation,
BookingStatusHistory,
    BookingAttachment,
    PaymentPlan,
    BookingKycRequest,
    KycStatus,
    BookingStatus,
)




def mask_mobile(mobile: str) -> str:
    if not mobile:
        return ""
    s = str(mobile)
    if len(s) <= 4:
        return "*" * len(s)
    return "*" * (len(s) - 4) + s[-4:]


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*" * (len(local) - 1)
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return masked_local + "@" + domain

from accounts.models import User
from clientsetup.models import PaymentPlan   # tum already import kar rahe ho upar
class ChannelPartnerSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "email"]   # agar mobile_number hai to yahan add kar sakte ho

    def get_full_name(self, obj):
        # Django User / custom User dono pe kaam karega
        return obj.get_full_name()
    

class PaymentPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentPlan
        # Simple option: saare fields bhej do. Agar limit chahiye to specific fields likh sakte ho.
        fields = "__all__"


# ⬇️ YAHAN ADD KAR
class CommaDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        # string aayi hai to commas hata do
        if isinstance(data, str):
            data = data.replace(",", "")
        return super().to_internal_value(data)



class BookingAdditionalChargeSerializer(serializers.ModelSerializer):
    amount = CommaDecimalField(max_digits=14, decimal_places=2)

    class Meta:
        model = BookingAdditionalCharge
        exclude = ("booking",)





class BookingKycRequestSerializer(serializers.ModelSerializer):
    decided_by_name = serializers.SerializerMethodField()
    project_name = serializers.CharField(source="project.name", read_only=True)
    unit_no = serializers.CharField(source="unit.unit_no", read_only=True)

    paid_amount = serializers.SerializerMethodField()
    is_fully_paid = serializers.SerializerMethodField()
    booking_id = serializers.IntegerField(
        source="booking.id",
        read_only=True,
    )

    class Meta:
        model = BookingKycRequest
        fields = [
            "id",
            "status",
            "amount",
            "snapshot",        # detailed JSON
            "project_name",
            "unit_no",
            "created_at",
            "decided_at",
            "decided_by_name",
            "paid_amount",
            "is_fully_paid",
            "decision_remarks",
                        "booking_id",
        ]

    def get_decided_by_name(self, obj):
        return obj.decided_by.get_full_name() if obj.decided_by_id else None


    def get_paid_amount(self, obj):
        # model property use kar rahe hain
        return obj.paid_amount

    def get_is_fully_paid(self, obj):
        return obj.is_fully_paid


class BookingApplicantSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(
        required=False,
        allow_null=True,
        input_formats=["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]
    )

    class Meta:
        model = BookingApplicant
        fields = [
            "id",
            "is_primary",
            "sequence",
            "title",
            "full_name",
            "relation",
            "date_of_birth",
            "email",
            "mobile_number",
            "pan_no",
            "aadhar_no",
            "pan_front",
            "pan_back",
            "aadhar_front",
            "aadhar_back",
        ]
        read_only_fields = ["id"]


class BookingAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    payment_amount = CommaDecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    class Meta:
        model = BookingAttachment
        fields = [
            "id",
            "label",
            "file",      # relative path
            "file_url",
            "doc_type",
            "payment_mode",
            "payment_ref_no",
            "bank_name",
            "payment_amount",
            "payment_date",
            "remarks",
            "created_at",
        ]
    def get_file_url(self, obj):
        request = self.context.get("request")
        if not obj.file:
            return None
        if request is None:
            return obj.file.url
        return request.build_absolute_uri(obj.file.url)
    








class BookingSerializer(serializers.ModelSerializer):
    """
    Single-shot booking create:
      - flat selection (unit_id)
      - booking info
      - applicants[]  (nested, optional)
      - attachments[] (nested, optional)
      - master OR custom payment plan
      - optional KYC link via kyc_request_id
    """
    sales_id = serializers.IntegerField(source="sales_lead_id", read_only=True)
    # ✅ nested – write + read
    applicants = BookingApplicantSerializer(many=True, required=False)
    attachments = BookingAttachmentSerializer(many=True, required=False)
    agreement_value = CommaDecimalField(max_digits=14, decimal_places=2)
    booking_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False
    )
    other_charges = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False
    )
    client_brand = serializers.SerializerMethodField(read_only=True)
    loan_amount_expected = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    signed_booking_file = serializers.FileField(
        required=False,
        allow_null=True,
    )
    signed_booking_file_url = serializers.SerializerMethodField()
    # ✅ optional KYC request link
    kyc_request_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True,
        help_text="Optional: link to an APPROVED BookingKycRequest",
    )
    parking_total_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False
    )
    parking_count = serializers.IntegerField(required=False)

    # Possession related charges snapshot
    share_application_money_membership_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    legal_compliance_charges_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    development_charges_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    electrical_water_piped_gas_charges_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    customer_base_price_psf = CommaDecimalField(
        max_digits=14, decimal_places=2,required=True, allow_null=True
    )
    provisional_maintenance_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    possessional_gst_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    parking_ids = serializers.PrimaryKeyRelatedField(
        source="parking_slots",
        queryset=ParkingInventory.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    parking_total_amount = CommaDecimalField(
        max_digits=14, decimal_places=2, required=False
    )
    parking_count = serializers.IntegerField(required=False, min_value=0)
    parking_slots = serializers.StringRelatedField(many=True, read_only=True)
    confirmed_by_name = serializers.SerializerMethodField()


    development_charges_psf = CommaDecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    discount_amount = CommaDecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    gst_percent = CommaDecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    stamp_duty_percent = CommaDecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    provisional_maintenance_months = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )

    # 🔹 Additional charges (name + amount)
    additional_charges = BookingAdditionalChargeSerializer(
        many=True,
        required=False,
    )

    # ✅ status ka human label
    status_label = serializers.CharField(
        source="get_status_display", read_only=True
    )

    # ✅ booking form / agreement PDF URL
    booking_form_pdf = serializers.SerializerMethodField()

    # write-only FK ids for clarity on FE
    unit_id = serializers.PrimaryKeyRelatedField(
        source="unit",
        queryset=Booking._meta.get_field("unit").remote_field.model.objects.all(),
        write_only=True,
    )
    sales_lead_id = serializers.PrimaryKeyRelatedField(
        source="sales_lead",
        queryset=Booking._meta.get_field("sales_lead").remote_field.model.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    channel_partner_id = serializers.PrimaryKeyRelatedField(
        source="channel_partner",
        queryset=Booking._meta.get_field("channel_partner").remote_field.model.objects.all(),
        required=False,
        allow_null=True,
        # write_only=True,
    )
    payment_plan_id = serializers.PrimaryKeyRelatedField(
        source="payment_plan",
        queryset=PaymentPlan.objects.all(),
        required=False,
        allow_null=True,
    )
    project_rera_no = serializers.CharField(
        source="project.rera_no",
        read_only=True,
    )
    channel_partner = ChannelPartnerSerializer(read_only=True)
    payment_plan = PaymentPlanSerializer(read_only=True)
    # read-only shape (for responses)
    project = serializers.StringRelatedField(read_only=True)
    tower = serializers.StringRelatedField(read_only=True)
    floor = serializers.StringRelatedField(read_only=True)
    unit = serializers.StringRelatedField(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    created_by_id = serializers.IntegerField(
        source="created_by.id", read_only=True
    )
    created_by_signature = serializers.SerializerMethodField()
    admin_name = serializers.SerializerMethodField()
    admin_signature = serializers.SerializerMethodField()
    sales_lead_id = serializers.PrimaryKeyRelatedField(
        source="sales_lead", queryset=SalesLead.objects.all(),
        required=False, allow_null=True, write_only=True,
    )
    sales_lead_name = serializers.CharField(
        source="sales_lead.first_name", read_only=True
    )
    class Meta:
        model = Booking
        fields = [
            "id",

            # FK ids (write)
            "unit_id",
            "sales_lead_id",
            "channel_partner_id",
            "payment_plan_id",
            "kyc_request_id",
        "created_by_id",
        "created_by_name",
        "created_by_signature",
        "confirmed_by_name",
        "parking_count",          # 🔰 NEW
        "customer_base_price_psf",        
        "parking_total_amount",   
            "confirmed_by_name",
            "sales_lead_name",
            "channel_partner",
            "payment_plan",
            # FK display (read)
            "project",
            "tower",
            "floor",
            "unit",
   "client_brand",
        "project_rera_no",   
            # Top bar
            "form_ref_no",
            "sales_id",
            "booking_date",
            "office_address",
        "development_charges_psf",
        "provisional_maintenance_months",
        "gst_percent",
        "stamp_duty_percent",
        "discount_amount",
        # Additional charges table
        "additional_charges",


            # Possession related charges
            "share_application_money_membership_amount",
            "legal_compliance_charges_amount",
            "development_charges_amount",
            "electrical_water_piped_gas_charges_amount",
            "provisional_maintenance_amount",
            "possessional_gst_amount",

            # Primary applicant snapshot
            "primary_title",
            "primary_full_name",
            "primary_email",
            "primary_mobile_number",
            "email_2",
            "phone_2",

            # Address & profile
            "permanent_address",
            "correspondence_address",
            "preferred_correspondence",
            "residential_status",

            # Flat info
            "super_builtup_sqft",
            "carpet_sqft",
            "balcony_sqft",
            "agreement_value",
            "agreement_value_words",
            "agreement_done",
            "parking_required",
            "parking_details",
            "parking_number",

            # Tax
            "gst_no",

            # KYC summary
            "kyc_status",
            # "kyc_deal_amount",  # yeh agar expose karna ho to add here

            # Payment plan
            "payment_plan_type",
            "custom_payment_plan",
            "parking_ids",        # write
            "parking_slots", 
            # Funding
            "loan_required",
            "loan_bank_name",
            "loan_amount_expected",

        "admin_name",
        "admin_signature",
        "client_brand",
            # Money
            "booking_amount",
            "other_charges",
            "total_advance",

            # Status
            "status",
            "status_label",
            "blocked_at",
            "booked_at",
            "cancelled_at",
            "cancelled_reason",

            # nested
            "applicants",
            "attachments",

            # 🔻 booking PDF
            "gst_no",
            "kyc_status",

        # 🔹 NEW
        "signed_booking_file",
        "signed_booking_file_url",

            # "kyc_deal_amount",
            "kyc_submitted_at",
            "kyc_approved_at",
            "booking_form_pdf",

            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "tower",
            "floor",
            "unit",
            "total_advance",
            "status",
            "blocked_at",
 "signed_booking_file_url",
            "booked_at",
            "cancelled_at",
"form_ref_no",
            "cancelled_reason",
            "created_at",
            "updated_at",
        ]



    def get_signed_booking_file_url(self, obj):
        file = getattr(obj, "signed_booking_file", None)
        if not file:
            return None

        request = self.context.get("request")
        url = file.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


    def _get_user_display_name(self, user):
        if not user:
            return None

        # 1) full_name
        name = (user.get_full_name() or "").strip()
        if name:
            return name

        # 2) username
        if getattr(user, "username", None):
            return user.username

        # 3) email
        if getattr(user, "email", None):
            return user.email

        return None


    def get_created_by_name(self, obj):
        user = getattr(obj, "created_by", None)
        return self._get_user_display_name(user)

    def get_confirmed_by_name(self, obj):
        user = getattr(obj, "confirmed_by", None)
        return self._get_user_display_name(user)


    def _get_signature_url(self, user):
        """
        User.signature ka absolute URL bana deta hai.
        """
        if not user or not getattr(user, "signature", None):
            return None

        sig = user.signature
        if not sig:
            return None

        request = self.context.get("request", None)
        url = sig.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_created_by_signature(self, obj):
        user = getattr(obj, "created_by", None)
        return self._get_signature_url(user)

    def get_admin_signature(self, obj):
        project = getattr(obj, "project", None)
        admin = getattr(project, "belongs_to", None) if project else None
        return self._get_signature_url(admin)

    def get_admin_name(self, obj):
        project = getattr(obj, "project", None)
        admin = getattr(project, "belongs_to", None) if project else None
        if not admin:
            return None
        full_name = admin.get_full_name()
        return full_name or admin.username or admin.email


    def get_client_brand(self, obj):
        """
        Return brand info of the admin who owns this project:
        booking.project.belongs_to -> ClientBrand
        """
        project = getattr(obj, "project", None)
        if not project:
            return None

        admin_user = getattr(project, "belongs_to", None)
        if not admin_user:
            return None

        # OneToOneField: admin.client_brand
        try:
            brand = admin_user.client_brand
        except ClientBrand.DoesNotExist:
            return None

        # Build absolute logo URL if possible
        request = self.context.get("request")
        logo_url = None
        if brand.logo:
            logo_url = brand.logo.url
            if request is not None:
                logo_url = request.build_absolute_uri(logo_url)

        return {
            "company_name": brand.company_name,
            "logo": logo_url,
            "primary_color": brand.primary_color,
            "secondary_color": brand.secondary_color,
        }

    def get_booking_form_pdf(self, obj):
        """
        Latest attachment with booking form / agreement.
        """
        att = (
            obj.attachments
            .filter(doc_type__in=["BOOKING_FORM_PDF", "AGREEMENT_PDF"])
            .order_by("-created_at")
            .first()
        )
        if not att or not att.file:
            return None

        request = self.context.get("request")
        url = att.file.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


    def validate(self, attrs):
        """
        Extra validation:
          - Inventory availability check (must be AVAILABLE)
          - Payment plan combo & slabs total.
        """

        # ----------------------------
        # 1) INVENTORY AVAILABILITY
        # ----------------------------
        # unit_id field ka source = "unit", to yahan attrs["unit"] milega
        unit = attrs.get("unit") or getattr(self.instance, "unit", None)

        if unit is None:
            # Normally field-level validation bhi karega, but clear error dena better:
            raise serializers.ValidationError({"unit_id": "Unit is required."})

        inv = getattr(unit, "inventory_items", None)

        if inv is None:
            # Unit ka inventory hi nahi bana
            raise serializers.ValidationError(
                {"unit_id": "No inventory is configured for this unit."}
            )

        # Ab availability check
        if inv.availability_status != AvailabilityStatus.AVAILABLE:
            # Human readable label bhi dikha sakte hain
            raise serializers.ValidationError(
                {
                    "unit_id": (
                        f"Selected unit is not available for booking. "
                        f"Current status: {inv.get_availability_status_display()}."
                    )
                }
            )

        # ----------------------------
        # 2) EXISTING PAYMENT PLAN LOGIC
        # ----------------------------
        payment_plan_type = attrs.get(
            "payment_plan_type",
            getattr(self.instance, "payment_plan_type", None),
        )
        custom_payment_plan = attrs.get(
            "custom_payment_plan",
            getattr(self.instance, "custom_payment_plan", None),
        )
        payment_plan = attrs.get(
            "payment_plan",
            getattr(self.instance, "payment_plan", None),
        )

        if not payment_plan_type:
            return attrs

        if payment_plan_type == "MASTER":
            if not payment_plan:
                raise serializers.ValidationError(
                    "payment_plan is required when payment_plan_type=MASTER."
                )
        elif payment_plan_type == "CUSTOM":
            if not custom_payment_plan:
                raise serializers.ValidationError(
                    "custom_payment_plan is required when payment_plan_type=CUSTOM."
                )
            slabs = (custom_payment_plan or {}).get("slabs") or []
            total_pct = sum(Decimal(str(s.get("percentage", 0))) for s in slabs)
            if total_pct != Decimal("100"):
                raise serializers.ValidationError(
                    "Custom payment plan slabs must total 100%."
                )
        else:
            raise serializers.ValidationError("Invalid payment_plan_type.")

        return attrs


    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)

        mobile_field = "primary_mobile_number"
        email_field = "primary_email"
        kyc_field = "kyc_deal_amount"

        # mask phone
        mobile_value = data.get(mobile_field)
        if mobile_value:
            data[mobile_field] = mask_mobile(mobile_value)

        # mask email
        email_value = data.get(email_field)
        if email_value:
            data[email_field] = mask_email(email_value)

        # KYC field hide logic (agar field ko Meta.fields me add karega to ye kaam karega)
        if kyc_field in data:
            if user is None:
                data.pop(kyc_field, None)
            else:
                role = getattr(user, "role", None)
                is_admin = (role == "ADMIN") or getattr(user, "is_superuser", False)
                if not is_admin:
                    data.pop(kyc_field, None)

        return data


    def create(self, validated_data):
        # Nested data nikaal lo
        parking_slots = validated_data.pop("parking_slots", [])
        applicants_data = validated_data.pop("applicants", [])
        attachments_data = validated_data.pop("attachments", [])
        kyc_request_id = validated_data.pop("kyc_request_id", None)
        additional_charges_data = validated_data.pop("additional_charges", [])
        parking_count = validated_data.get("parking_count")
        if parking_count is None:
            validated_data["parking_count"] = len(parking_slots)

        # --- Unit se Project/Tower/Floor derive karo ---
        unit = validated_data.get("unit")
        if not unit:
            raise serializers.ValidationError({"unit_id": "Unit is required."})

        if not validated_data.get("project", None):
            project = getattr(unit, "project", None)
            if project is None and hasattr(unit, "tower"):
                project = getattr(unit.tower, "project", None)
            if project is None:
                raise serializers.ValidationError(
                    "Could not derive project from unit. Please check Unit → Project relation."
                )
            validated_data["project"] = project

        if "tower" in [f.name for f in Booking._meta.get_fields()]:
            if not validated_data.get("tower", None) and hasattr(unit, "tower"):
                validated_data["tower"] = unit.tower

        if "floor" in [f.name for f in Booking._meta.get_fields()]:
            if not validated_data.get("floor", None) and hasattr(unit, "floor"):
                validated_data["floor"] = unit.floor

        # created_by fill
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not validated_data.get("created_by"):
            validated_data["created_by"] = user

        now = timezone.now()

        with transaction.atomic():
            # 1) base booking
            booking = Booking.objects.create(**validated_data)

            # 2) parking allocations
            for idx, p in enumerate(parking_slots):
                BookingParkingAllocation.objects.create(
                    booking=booking,
                    parking=p,
                    is_primary=(idx == 0),
                )

            # 3) nested applicants / attachments
            for idx, app_data in enumerate(applicants_data, start=1):
                app_data.setdefault("sequence", idx)
                BookingApplicant.objects.create(booking=booking, **app_data)

            for att_data in attachments_data:
                BookingAttachment.objects.create(booking=booking, **att_data)

            for ac in additional_charges_data:
                BookingAdditionalCharge.objects.create(
                    booking=booking,
                    label=ac.get("label", ""),
                    amount=ac.get("amount") or 0,
                )


            update_fields = []
            kyc = None

            # 4) KYC copy (status copy, but booking BOOKED nahi karenge yahan)
            if kyc_request_id:
                try:
                    kyc = BookingKycRequest.objects.select_for_update().get(
                        pk=kyc_request_id
                    )
                except BookingKycRequest.DoesNotExist:
                    raise serializers.ValidationError(
                        {"kyc_request_id": "Invalid KYC request."}
                    )

                booking.kyc_status = kyc.status

                if kyc.status == KycStatus.APPROVED:
                    booking.kyc_deal_amount = kyc.amount
                    booking.kyc_approved_at = kyc.decided_at
                    booking.kyc_approved_by = kyc.decided_by
                    update_fields.extend(
                        [
                            "kyc_status",
                            "kyc_deal_amount",
                            "kyc_approved_at",
                            "kyc_approved_by",
                        ]
                    )
                else:
                    update_fields.append("kyc_status")

            # 5) 🔴 Booking CREATE = hamesha DRAFT + BLOCKED
            booking.status = BookingStatus.DRAFT
            booking.blocked_at = now
            update_fields.extend(["status", "blocked_at"])
            booking.save(update_fields=update_fields)

            # 6) 🔒 Flat Inventory ko BLOCK + history
            unit = booking.unit
            inv = getattr(unit, "inventory_items", None)

            if inv:
                # block_period_days set ho to wahi, warna e.g. 7 days fallback
                days = inv.block_period_days or 7
                inv.block(
                    days=days,
                    reason=f"Blocked for Booking #{booking.id}",
                    changed_by=user,
                )
            else:
                try:
                    unit.status = UnitStatus.BLOCKED
                except Exception:
                    unit.status = "BLOCKED"
                unit.save(update_fields=["status"])

            # Parking block (tumhara existing logic)
            for p in parking_slots:
                if p.availability_status != AvailabilityStatus.BLOCKED:
                    p.availability_status = AvailabilityStatus.BLOCKED
                    p.save(update_fields=["availability_status"])

            # Booking status history
            BookingStatusHistory.objects.create(
                booking=booking,
                old_status="",
                new_status=booking.status,
                old_kyc_status="",
                new_kyc_status=booking.kyc_status,
                action="CREATE",
                reason="Booking created",
                changed_by=user,
            )

        return booking


    def update(self, instance, validated_data):
        validated_data.pop("applicants", None)
        validated_data.pop("attachments", None)
        validated_data.pop("kyc_request_id", None)
        additional_charges_data = validated_data.pop(
            "additional_charges", None
        )

        instance = super().update(instance, validated_data)

        # If FE sends additional_charges, replace existing ones
        if additional_charges_data is not None:
            instance.additional_charges.all().delete()
            for ac in additional_charges_data:
                BookingAdditionalCharge.objects.create(
                    booking=instance,
                    label=ac.get("label", ""),
                    amount=ac.get("amount") or 0,
                )

        return instance






class BookingKycRequestCreateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    unit_id = serializers.IntegerField()
    amount = CommaDecimalField(max_digits=14, decimal_places=2)

    def validate(self, attrs):
        try:
            project = Project.objects.get(pk=attrs["project_id"])
        except Project.DoesNotExist:
            raise serializers.ValidationError({"project_id": "Invalid project."})

        try:
            unit = Unit.objects.get(pk=attrs["unit_id"])
        except Unit.DoesNotExist:
            raise serializers.ValidationError({"unit_id": "Invalid unit."})

        attrs["project"] = project
        attrs["unit"] = unit
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        project = validated_data["project"]
        unit = validated_data["unit"]
        amount = validated_data["amount"]

        snapshot = BookingKycRequest.build_snapshot(
            project, unit, agreement_value=amount
        )

        kyc = BookingKycRequest.objects.create(
            project=project,
            unit=unit,
            amount=amount,
            snapshot=snapshot,
            created_by=getattr(request, "user", None),
            status=KycStatus.PENDING,
        )
        return kyc

