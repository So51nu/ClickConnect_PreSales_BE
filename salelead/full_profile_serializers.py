# salelead/full_profile_serializers.py

from rest_framework import serializers

from .models import (
    SalesLead,
    SalesLeadAddress,
    SalesLeadCPInfo,
    SalesLeadPersonalInfo,
    SalesLeadProfessionalInfo,
    SalesLeadProposalDocument,
    InterestedLeadUnit,
)
from setup.models import OfferingType  # for offering_types mini info


# ---------- Small / nested serializers ----------

class SalesLeadAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesLeadAddress
        exclude = ("id", "sales_lead")


class SalesLeadCPInfoSerializer(serializers.ModelSerializer):
    cp_user_name = serializers.SerializerMethodField()
    cp_user_email = serializers.SerializerMethodField()

    class Meta:
        model = SalesLeadCPInfo
        fields = (
            "cp_user",
            "cp_user_name",
            "cp_user_email",
            "referral_code",
        )

    def get_cp_user_name(self, obj):
        u = obj.cp_user
        if not u:
            return None
        if hasattr(u, "get_full_name") and u.get_full_name():
            return u.get_full_name()
        name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return name or getattr(u, "username", None)

    def get_cp_user_email(self, obj):
        u = obj.cp_user
        return getattr(u, "email", None) if u else None


class SalesLeadPersonalInfoSerializer(serializers.ModelSerializer):
    visiting_on_behalf_name = serializers.SerializerMethodField()
    current_residence_ownership_name = serializers.SerializerMethodField()
    family_size_name = serializers.SerializerMethodField()
    possession_desired_in_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesLeadPersonalInfo
        fields = (
            "date_of_birth",
            "date_of_anniversary",
            "already_part_of_family",
            "secondary_email",
            "alternate_mobile",
            "alternate_tel_res",
            "alternate_tel_off",
            "visiting_on_behalf",
            "visiting_on_behalf_name",
            "current_residence_ownership",
            "current_residence_ownership_name",
            "current_residence_type",
            "family_size",
            "family_size_name",
            "possession_desired_in",
            "possession_desired_in_name",
            "facebook",
            "twitter",
            "linkedin",
        )

    def _safe_label(self, obj):
        return str(obj) if obj else None

    def get_visiting_on_behalf_name(self, obj):
        return self._safe_label(obj.visiting_on_behalf)

    def get_current_residence_ownership_name(self, obj):
        return self._safe_label(obj.current_residence_ownership)

    def get_family_size_name(self, obj):
        return self._safe_label(obj.family_size)

    def get_possession_desired_in_name(self, obj):
        return self._safe_label(obj.possession_desired_in)


class SalesLeadProfessionalInfoSerializer(serializers.ModelSerializer):
    occupation_name = serializers.SerializerMethodField()
    designation_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesLeadProfessionalInfo
        fields = (
            "occupation",
            "occupation_name",
            "organization_name",
            "office_location",
            "office_pincode",
            "designation",
            "designation_name",
        )

    def get_occupation_name(self, obj):
        return str(obj.occupation) if obj.occupation else None

    def get_designation_name(self, obj):
        return str(obj.designation) if obj.designation else None


class SalesLeadProposalDocumentSerializer(serializers.ModelSerializer):
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesLeadProposalDocument
        fields = ("id", "file", "file_name", "created_at")

    def get_file_name(self, obj):
        if not obj.file:
            return None
        return getattr(obj.file, "name", None)


class OfferingTypeMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferingType
        fields = ("id", "name")


class InterestedLeadUnitSerializer(serializers.ModelSerializer):
    unit_label = serializers.SerializerMethodField()

    class Meta:
        model = InterestedLeadUnit
        fields = ("id", "unit", "unit_label", "is_primary")

    def get_unit_label(self, obj):
        # Adjust if you want more specific (unit_number, tower, etc.)
        return str(obj.unit) if obj.unit else None


# ---------- Main FULL Lead serializer (for view) ----------

# salelead/serializers.py
from decimal import Decimal
from rest_framework import serializers

from .models import PaymentLead


class PaymentLeadSerializer(serializers.ModelSerializer):
    # Read-only helper fields
    lead_full_name = serializers.CharField(
        source="lead.get_full_name",
        read_only=True,
    )
    project_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PaymentLead
        fields = [
            "id",

            # relations
            "lead",
            "lead_full_name",
            "project",
            "project_name",
            "booking",

            # core payment info
            "payment_type",
            "payment_method",
            "amount",
            "payment_date",
            "status",
            "notes",

            # ONLINE / POS
            "payment_mode",
            "transaction_no",
            "pos_slip_image",

            # DRAFT / CHEQUE
            "cheque_number",
            "cheque_date",
            "bank_name",
            "ifsc_code",
            "branch_name",
            "cheque_image",

            # NEFT / RTGS
            "neft_rtgs_ref_no",

            # meta
            "created_by",
            "created_by_name",
        ]
        read_only_fields = [
            "id",
            "project",
            "project_name",
            "created_by",
            "created_by_name",
            "lead_full_name",
        ]

    # --------- helper fields ----------

    def get_project_name(self, obj):
        if not obj.project:
            return None
        # dono cases cover: project_name ya name
        return (
            getattr(obj.project, "project_name", None)
            or getattr(obj.project, "name", None)
            or str(obj.project)
        )

    def get_created_by_name(self, obj):
        user = obj.created_by
        if not user:
            return None

        if hasattr(user, "get_full_name") and user.get_full_name():
            return user.get_full_name()

        name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        return name or getattr(user, "username", None)

    # --------- method-wise validation ----------

    def validate(self, attrs):
        from .models import PaymentLead as PaymentLeadModel

        instance = self.instance
        errors = {}

        payment_method = attrs.get("payment_method") or getattr(
            instance, "payment_method", None
        )
        amount = attrs.get("amount") or getattr(instance, "amount", None)

        # Amount check
        if amount is not None and amount <= Decimal("0"):
            errors["amount"] = "Amount must be greater than 0."

        # ONLINE / POS: transaction_no required
        if payment_method in (
            PaymentLeadModel.PaymentMethod.ONLINE,
            PaymentLeadModel.PaymentMethod.POS,
        ):
            transaction_no = attrs.get("transaction_no") or getattr(
                instance, "transaction_no", None
            )
            if not transaction_no:
                errors["transaction_no"] = "Transaction No is required for ONLINE/POS payments."

        # DRAFT / CHEQUE: multiple required fields
        if payment_method == PaymentLeadModel.PaymentMethod.DRAFT_CHEQUE:
            cheque_number = attrs.get("cheque_number") or getattr(
                instance, "cheque_number", None
            )
            cheque_date = attrs.get("cheque_date") or getattr(
                instance, "cheque_date", None
            )
            bank_name = attrs.get("bank_name") or getattr(
                instance, "bank_name", None
            )
            ifsc_code = attrs.get("ifsc_code") or getattr(
                instance, "ifsc_code", None
            )
            branch_name = attrs.get("branch_name") or getattr(
                instance, "branch_name", None
            )

            if not cheque_number:
                errors["cheque_number"] = "Cheque Number is required for Draft/Cheque payments."
            if not cheque_date:
                errors["cheque_date"] = "Cheque Date is required for Draft/Cheque payments."
            if not bank_name:
                errors["bank_name"] = "Bank Name is required for Draft/Cheque payments."
            if not ifsc_code:
                errors["ifsc_code"] = "IFSC Code is required for Draft/Cheque payments."
            if not branch_name:
                errors["branch_name"] = "Branch Name is required for Draft/Cheque payments."

        # NEFT / RTGS: ref no required
        if payment_method == PaymentLeadModel.PaymentMethod.NEFT_RTGS:
            ref_no = attrs.get("neft_rtgs_ref_no") or getattr(
                instance, "neft_rtgs_ref_no", None
            )
            if not ref_no:
                errors["neft_rtgs_ref_no"] = "NEFT / RTGS Ref.No is required for NEFT/RTGS payments."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


# ---------- Main FULL Lead serializer (for view) ----------

class SalesLeadFullDetailSerializer(serializers.ModelSerializer):
    # base display helpers
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    # FK label fields (project / taxonomy / owners etc.)
    project_name = serializers.CharField(
        source="project.project_name", read_only=True
    )
    payments = PaymentLeadSerializer(many=True, read_only=True)

    classification_name = serializers.CharField(
        source="classification.name", read_only=True, default=None
    )
    sub_classification_name = serializers.CharField(
        source="sub_classification.name", read_only=True, default=None
    )
    source_name = serializers.CharField(
        source="source.name", read_only=True, default=None
    )
    sub_source_name = serializers.CharField(
        source="sub_source.name", read_only=True, default=None
    )
    status_name = serializers.CharField(
        source="status.name", read_only=True, default=None
    )
    sub_status_name = serializers.CharField(
        source="sub_status.name", read_only=True, default=None
    )
    purpose_name = serializers.CharField(
        source="purpose.name", read_only=True, default=None
    )

    channel_partner_name = serializers.SerializerMethodField()

    current_owner_name = serializers.SerializerMethodField()
    first_owner_name = serializers.SerializerMethodField()
    assign_to_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    # M2M – expose richer list with names as well
    offering_types_list = OfferingTypeMiniSerializer(
        source="offering_types", many=True, read_only=True
    )

    # nested one-to-one/one-to-many
    address = SalesLeadAddressSerializer(read_only=True)
    cp_info = SalesLeadCPInfoSerializer(read_only=True)
    personal_info = SalesLeadPersonalInfoSerializer(read_only=True)
    professional_info = SalesLeadProfessionalInfoSerializer(read_only=True)
    proposal_documents = SalesLeadProposalDocumentSerializer(
        many=True, read_only=True
    )
    interested_unit_links = InterestedLeadUnitSerializer(
        many=True, read_only=True
    )

    class Meta:
        model = SalesLead
        fields = (
            # core IDs
            "id",

            # name helpers
            "first_name",
            "last_name",
            "full_name",

            # contact
            "email",
            "mobile_number",
            "tel_res",
            "tel_office",

            # project
            "project",
            "project_name",

            # site visit
            "last_site_visit_status",
            "last_site_visit_at",

            # CP info at lead level
            "channel_partner",
            "channel_partner_name",
            "unknown_channel_partner",

            # misc
            "walking",
            "company",
            "budget",
            "annual_income",

            # taxonomy FKs + labels
            "classification",
            "classification_name",
            "sub_classification",
            "sub_classification_name",
            "source",
            "source_name",
            "sub_source",
            "sub_source_name",
            "status",
            "status_name",
            "sub_status",
            "sub_status_name",
            "purpose",
            "purpose_name",

            # ownership
            "current_owner",
            "current_owner_name",
            "first_owner",
            "first_owner_name",
            "assign_to",
            "assign_to_name",

            # created_by
            "created_by",
            "created_by_name",

            # M2M offerings
            "offering_types",
            "offering_types_list",
            "payments",
            # Link to opportunity (if any)
            "source_opportunity",

            # nested detailed sections
            "address",
            "cp_info",
            "personal_info",
            "professional_info",
            "proposal_documents",
            "interested_unit_links",

            # timestamps (from TimeStamped)
            "created_at",
            "updated_at",
        )

    # ----- FK label helpers -----

    def _user_name(self, u):
        if not u:
            return None
        if hasattr(u, "get_full_name") and u.get_full_name():
            return u.get_full_name()
        name = f"{getattr(u, 'first_name', '')} {getattr(u, 'last_name', '')}".strip()
        return name or getattr(u, "username", None)

    def get_channel_partner_name(self, obj):
        cp = obj.channel_partner
        if not cp:
            return None
        # try common possibilities; adjust if you have a specific field
        for attr in ("name", "company_name", "full_name"):
            val = getattr(cp, attr, None)
            if val:
                return val
        return str(cp)

    def get_current_owner_name(self, obj):
        return self._user_name(obj.current_owner)

    def get_first_owner_name(self, obj):
        return self._user_name(obj.first_owner)

    def get_assign_to_name(self, obj):
        return self._user_name(obj.assign_to)

    def get_created_by_name(self, obj):
        return self._user_name(obj.created_by)





class SalesLeadLookupSerializer(SalesLeadFullDetailSerializer):
    last_update = serializers.SerializerMethodField()
    last_stage = serializers.SerializerMethodField()

    class Meta(SalesLeadFullDetailSerializer.Meta):
        fields = SalesLeadFullDetailSerializer.Meta.fields + (
            "last_update",
            "last_stage",
        )

    def _user_display(self, user):
        if not user:
            return None
        if hasattr(user, "get_full_name"):
            name = (user.get_full_name() or "").strip()
            if name:
                return name
        return getattr(user, "email", None) or getattr(user, "username", None)

    def get_last_update(self, obj: SalesLead):
        # force ordering here, ignore whatever prefetch did
        upd = obj.updates.order_by("-event_date", "-id").first()
        if not upd:
            return None

        return {
            "id": upd.id,
            "type": upd.update_type,
            "title": upd.title,
            "info": upd.info,
            "event_date": upd.event_date,
            "activity_status": getattr(upd.activity_status, "name", None),
            "created_by": self._user_display(upd.created_by),
        }

    def get_last_stage(self, obj: SalesLead):
        # same idea for stage history
        hist = obj.stage_history.order_by("-event_date", "-id").first()
        if not hist:
            return None

        return {
            "id": hist.id,
            "stage": getattr(hist.stage, "name", None),
            "status": getattr(hist.status, "name", None),
            "sub_status": getattr(hist.sub_status, "name", None),
            "event_date": hist.event_date,
            "created_by": self._user_display(hist.created_by),
        }
