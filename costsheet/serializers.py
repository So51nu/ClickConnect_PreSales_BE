from rest_framework import serializers
from clientsetup.models import Project
from .models import CostSheetTemplate, ProjectCostSheetTemplate
from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from salelead.models import SalesLead
from clientsetup.models import Project, Inventory, CommercialOffer
from .models import (
    CostSheet,
    CostSheetAdditionalCharge,
    CostSheetAppliedOffer,
    ProjectCostSheetTemplate,
)
from clientsetup.models import PaymentPlan, PaymentSlab, Project, Inventory
from salelead.models import SalesLead



class CostSheetTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostSheetTemplate
        fields = [
            "id",
            "created_by",
            "company_name",
            "company_logo",
            "quotation_header",
            "quotation_subheader",
            "validity_days",
            "gst_percent",
            "stamp_duty_percent",
            "registration_amount",
            "legal_fee_amount",
            "terms_and_conditions",
            "config",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user
        return super().create(validated_data)


class ProjectCostSheetTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCostSheetTemplate
        fields = [
            "id",
            "created_by",
            "project",
            "template",
            "is_active",
            "extra_charges",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user
        return super().create(validated_data)


class ProjectCostSheetTemplateMiniSerializer(serializers.ModelSerializer):
    """Short version used inside nested template response."""

    class Meta:
        model = ProjectCostSheetTemplate
        fields = ["id", "project", "is_active", "extra_charges"]


class CostSheetTemplateWithProjectMappingSerializer(serializers.ModelSerializer):
    """
    Template + mapping for given project (if mapping exists).
    """

    mapping = serializers.SerializerMethodField()

    class Meta:
        model = CostSheetTemplate
        fields = [
            "id",
            "company_name",
            "company_logo",
            "quotation_header",
            "quotation_subheader",
            "validity_days",
            "gst_percent",
            "stamp_duty_percent",
            "registration_amount",
            "legal_fee_amount",
            "terms_and_conditions",
            "config",
            "mapping",
        ]

    def get_mapping(self, obj):
        request = self.context.get("request")
        project_id = self.context.get("project_id")
        if not project_id:
            return None

        qs = obj.project_mappings.filter(project_id=project_id)

        # Optional: restrict to same admin who owns template
        if request is not None:
            qs = qs.filter(created_by=request.user)

        mapping = qs.first()
        if not mapping:
            return None

        return ProjectCostSheetTemplateMiniSerializer(mapping).data


class CostSheetTemplatePayloadSerializer(serializers.Serializer):
    """
    Inner serializer for 'template' object in bulk API.
    This matches CostSheetTemplate fields (except created_by).
    """

    company_name = serializers.CharField(max_length=255)
    company_logo = serializers.ImageField(required=False, allow_null=True)

    quotation_header = serializers.CharField(max_length=255)
    quotation_subheader = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )

    validity_days = serializers.IntegerField(required=False, default=7)

    gst_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    stamp_duty_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    registration_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    legal_fee_amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    terms_and_conditions = serializers.CharField(required=False, allow_blank=True)
    config = serializers.JSONField(required=False, allow_null=True)


class CostSheetTemplateBulkCreateOrMapSerializer(serializers.Serializer):
    """
    Bulk API:

    Mode 1: Create NEW template + map to multiple projects
    ------------------------------------------------------
    {
      "template": {
        "company_name": "...",
        "company_logo": null,
        "quotation_header": "Cost Sheet Header",
        "quotation_subheader": "Sub header",
        "validity_days": 7,
        "gst_percent": "5.00",
        "stamp_duty_percent": "6.00",
        "registration_amount": "35000.00",
        "legal_fee_amount": "15000.00",
        "terms_and_conditions": "Prices are subject to change...",
        "config": null
      },
      "projects": [12, 122, 32],
      "extra_charges": {"maintenance_deposit": 50000},
      "is_active": true
    }

    Mode 2: Use EXISTING template + map to multiple projects
    --------------------------------------------------------
    {
      "template_id": 3,
      "projects": [12, 122, 32],
      "extra_charges": null,
      "is_active": true
    }

    For each project, mapping is created ONLY if not already present.
    """

    template = CostSheetTemplatePayloadSerializer(required=False)
    template_id = serializers.IntegerField(required=False)

    projects = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False
    )

    extra_charges = serializers.JSONField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        template_data = attrs.get("template")
        template_id = attrs.get("template_id")

        if not template_data and not template_id:
            raise serializers.ValidationError(
                "Either 'template' or 'template_id' is required."
            )

        if template_data and template_id:
            raise serializers.ValidationError(
                "Provide only one of 'template' or 'template_id', not both."
            )

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        template_data = validated_data.get("template")
        template_id = validated_data.get("template_id")
        project_ids = validated_data["projects"]
        extra_charges = validated_data.get("extra_charges")
        is_active = validated_data.get("is_active", True)

        # ---- 1) Resolve template (new or existing) ----
        if template_id:
            try:
                template = CostSheetTemplate.objects.get(
                    id=template_id,
                    created_by=user,  # only templates owned by this admin
                )
            except CostSheetTemplate.DoesNotExist:
                raise serializers.ValidationError(
                    {"template_id": "Template not found or not owned by current admin."}
                )
        else:
            # new template
            template = CostSheetTemplate.objects.create(
                created_by=user,
                **template_data,
            )

        # ---- 2) Validate project list ----
        projects = list(Project.objects.filter(id__in=project_ids))
        project_map = {p.id: p for p in projects}

        missing = sorted(set(project_ids) - set(project_map.keys()))
        if missing:
            raise serializers.ValidationError(
                {"projects": f"Invalid project ids: {missing}"}
            )

        # ---- 3) Create mappings only when not existing ----
        mappings = []
        for pid in project_ids:
            project = project_map[pid]
            mapping, created = ProjectCostSheetTemplate.objects.get_or_create(
                project=project,
                template=template,
                defaults={
                    "created_by": user,
                    "is_active": is_active,
                    "extra_charges": extra_charges,
                },
            )
            # If already existed, we leave it as-is (idempotent)
            mappings.append(mapping)

        return {
            "template": template,
            "mappings": mappings,
        }

    def to_representation(self, instance):
        template = instance["template"]
        mappings = instance["mappings"]

        template_data = CostSheetTemplateSerializer(
            template, context=self.context
        ).data
        mapping_data = ProjectCostSheetTemplateSerializer(
            mappings, many=True, context=self.context
        ).data

        return {
            "template": template_data,
            "mappings": mapping_data,
        }


class CostSheetAdditionalChargeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CostSheetAdditionalCharge
        fields = ("id", "name", "amount", "sort_order", "is_taxable")


class CostSheetAppliedOfferInputSerializer(serializers.Serializer):
    """
    For POST/PATCH only – simple input.
    """
    offer_id = serializers.IntegerField()
    applied_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)


class CostSheetAppliedOfferSerializer(serializers.ModelSerializer):
    offer_name = serializers.CharField(source="offer.name", read_only=True)
    offer_code = serializers.CharField(source="offer.code", read_only=True)

    class Meta:
        model = CostSheetAppliedOffer
        fields = ("id", "offer", "offer_name", "offer_code", "applied_amount", "notes")



class PaymentSlabOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentSlab
        fields = ("id", "order_index", "name", "percentage", "days")


class PaymentPlanOutputSerializer(serializers.ModelSerializer):
    slabs = PaymentSlabOutputSerializer(many=True, read_only=True)

    class Meta:
        model = PaymentPlan
        fields = ("id", "code", "name", "total_percentage", "slabs")

from decimal import Decimal
class CostSheetShortSerializer(serializers.ModelSerializer):
    """
    Lightweight summary for listing quotations by prepared_by.
    """
    prepared_by_name = serializers.CharField(
        source="prepared_by.get_full_name",
        read_only=True,
    )
    prepared_by_username = serializers.CharField(
        source="prepared_by.username",
        read_only=True,
    )

    class Meta:
        model = CostSheet
        fields = [
            "id",
            "quotation_no",
            "date",
            "valid_till",
            "status",
            "customer_name",
            "project_name",
            "net_base_value",
            "net_payable_amount",
            "prepared_by_name",
            "prepared_by_username",
            "created_at",
        ]





class CostSheetSerializer(serializers.ModelSerializer):
    # FK ids from FE
    lead_id = serializers.PrimaryKeyRelatedField(
        source="lead",
        queryset=SalesLead.objects.all(),
        write_only=True,
    )
    project_id = serializers.PrimaryKeyRelatedField(
        source="project",
        queryset=Project.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    inventory_id = serializers.PrimaryKeyRelatedField(
        source="inventory",
        queryset=Inventory.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    project_template_id = serializers.PrimaryKeyRelatedField(
        source="project_template",
        queryset=ProjectCostSheetTemplate.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    amount_before_taxes = serializers.SerializerMethodField()
    final_amount_incl_taxes = serializers.SerializerMethodField()

    status_label = serializers.SerializerMethodField()
    quotation_pdf = serializers.SerializerMethodField()
    quotation_pdf_url = serializers.ReadOnlyField()

    # ---------- NEW prepared_by fields (read-only) ----------
    prepared_by_id = serializers.IntegerField(
        source="prepared_by.id", read_only=True
    )
    prepared_by_name = serializers.CharField(
        source="prepared_by.get_full_name", read_only=True
    )
    prepared_by_username = serializers.CharField(
        source="prepared_by.username", read_only=True
    )
    quotation_pdf_url = serializers.ReadOnlyField()
    # nested inputs
    additional_charges = CostSheetAdditionalChargeSerializer(
        many=True, write_only=True, required=False
    )
    applied_offers = CostSheetAppliedOfferInputSerializer(
        many=True, write_only=True, required=False
    )

    # nested outputs
    additional_charges_detail = CostSheetAdditionalChargeSerializer(
        source="additional_charges",
        many=True,
        read_only=True,
    )
    applied_offers_detail = CostSheetAppliedOfferSerializer(
        source="applied_offers",
        many=True,
        read_only=True,
    )

    payment_plan_detail = PaymentPlanOutputSerializer(
        source="payment_plan",
        read_only=True,
    )

    class Meta:
        model = CostSheet
        fields = [
            "id",
            # FK inputs
            "lead_id",
            "project_id",
            "inventory_id",
            "project_template_id",
            "amount_before_taxes",
            "final_amount_incl_taxes",
            "quotation_no",
            "date",
            "status_label",
            "valid_till",
            "status",
            # prepared_by
            "prepared_by_id",
            "prepared_by_name",
            "prepared_by_username",

            # customer + unit snapshot
            "customer_name",
            "customer_contact_person",
            "customer_phone",
            "customer_email",
            "project_name",
            "tower_name",
            "floor_number",
            "unit_no",
            "customer_snapshot",
            "unit_snapshot",

            # base pricing
            "base_area_sqft",
            "base_rate_psf",
            "base_value",
            "discount_percent",
            "discount_amount",
            "net_base_value",

            # plan
            "payment_plan_type",
            "payment_plan",
            "custom_payment_plan",
            "payment_plan_detail",

            "quotation_pdf_url",
            "quotation_pdf",

            # taxes
            "gst_percent",
            "gst_amount",
            "stamp_duty_percent",
            "stamp_duty_amount",
            "registration_amount",
            "legal_fee_amount",

            # 🔹 NEW: parking / statutory block
            "parking_count",
            "per_parking_price",
            "parking_amount",
            "share_application_money_membership_amount",
            "legal_compliance_charges_amount",
            "development_charges_amount",
            "electrical_water_piped_gas_charges_amount",
            "provisional_maintenance_amount",
            "possessional_gst_amount",

            # totals
            "additional_charges_total",
            "offers_total",
            "net_payable_amount",

            # texts
            "terms_and_conditions",
            "notes",

            # nested write
            "additional_charges",
            "applied_offers",

            # nested read
            "additional_charges_detail",
            "applied_offers_detail",

            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "created_at",
            "updated_at",
            "additional_charges_detail",
            "applied_offers_detail",
            "payment_plan_detail",
            "prepared_by_id",
            "prepared_by_name",
            "prepared_by_username",
            "status_label",
            "quotation_no",
            "quotation_pdf",
            "quotation_pdf_url",
        )
        extra_kwargs = {
            # 👇 important
            "payment_plan": {"required": False, "allow_null": True},
            "payment_plan_type": {"required": False, "allow_null": True},
        }
    def create(self, validated_data):
        request = self.context.get("request")

        add_charges_data = validated_data.pop("additional_charges", [])
        applied_offers_data = validated_data.pop("applied_offers", [])

        # yahi pe DB me prepared_by set ho raha hai
        if request and request.user.is_authenticated:
            validated_data.setdefault("prepared_by", request.user)

        instance = CostSheet(**validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(e.message_dict)

        instance.save()

        # ... (baaki additional_charges / applied_offers logic same)
        for idx, ch in enumerate(add_charges_data, start=1):
            if ch.get("sort_order") is None:
                ch["sort_order"] = idx
            CostSheetAdditionalCharge.objects.create(
                costsheet=instance,
                **ch,
            )

        for row in applied_offers_data:
            offer_id = row.get("offer_id")
            if not offer_id:
                continue
            try:
                offer = CommercialOffer.objects.get(pk=offer_id)
            except CommercialOffer.DoesNotExist:
                continue

            CostSheetAppliedOffer.objects.create(
                costsheet=instance,
                offer=offer,
                applied_amount=row.get("applied_amount"),
                notes=row.get("notes", ""),
            )

        return instance

    def get_amount_before_taxes(self, obj):
        base = obj.net_base_value or Decimal("0")
        charges = obj.additional_charges_total or Decimal("0")

        # NEW: all statutory / parking charges
        statutory = (
            (obj.parking_amount or Decimal("0"))
            + (obj.share_application_money_membership_amount or Decimal("0"))
            + (obj.legal_compliance_charges_amount or Decimal("0"))
            + (obj.development_charges_amount or Decimal("0"))
            + (obj.electrical_water_piped_gas_charges_amount or Decimal("0"))
            + (obj.provisional_maintenance_amount or Decimal("0"))
        )

        return base + charges + statutory

    def get_final_amount_incl_taxes(self, obj):
        base_plus_charges = self.get_amount_before_taxes(obj)
        taxes = (
            (obj.gst_amount or Decimal("0"))
            + (obj.stamp_duty_amount or Decimal("0"))
            + (obj.registration_amount or Decimal("0"))
            + (obj.legal_fee_amount or Decimal("0"))
            + (obj.possessional_gst_amount or Decimal("0"))  # NEW
        )
        return base_plus_charges + taxes


    # 👇 NEW
    def get_status_label(self, obj):
        # defensive, but status should be present
        return obj.get_status_display() if getattr(obj, "status", None) else None

    # 👇 NEW
    def get_quotation_pdf(self, obj):
        """
        Absolute URL for quotation PDF.

        - Prefer attachments with doc_type in ["QUOTATION_PDF", "QUOTE_PDF"]
        - Fallback to latest attachment with any doc_type
        """
        request = self.context.get("request")
        if not request:
            return None

        # Try specific doc types first
        att = (
            obj.attachments
            .filter(doc_type__in=["QUOTATION_PDF", "QUOTE_PDF"])
            .order_by("-created_at")
            .first()
        ) or obj.attachments.order_by("-created_at").first()

        if att and att.file:
            return request.build_absolute_uri(att.file.url)

        return None
