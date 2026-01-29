from decimal import Decimal
from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from rest_framework import serializers
from django.db import transaction
from .models import Inventory, InventoryDocument, AvailabilityStatus, InventoryStatus
from rest_framework import serializers
from .models import Inventory, InventoryDocument


class InventoryDocumentWriteSerializer(serializers.ModelSerializer):
    # file: use multipart for single create; for bulk you can pass file later per-inventory
    class Meta:
        model = InventoryDocument
        fields = ("id", "doc_type", "file", "original_name")
        extra_kwargs = {
            "id": {"read_only": True},
            "original_name": {"required": False, "allow_blank": True},
        }



from rest_framework import serializers
from .models import Inventory, InventoryDocument
from clientsetup.models import Project, Tower, Floor, Unit  # if needed
# and unit config models if they are in other apps

class InventorySerializer(serializers.ModelSerializer):
    documents = InventoryDocumentWriteSerializer(many=True, required=False)

    # 🔹 Extra read-only fields for display
    project_name       = serializers.SerializerMethodField()
    tower_name         = serializers.SerializerMethodField()
    floor_number       = serializers.SerializerMethodField()
    unit_no            = serializers.SerializerMethodField()
    unit_type_name     = serializers.SerializerMethodField()
    configuration_name = serializers.SerializerMethodField()
    facing_name        = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = (
            "id",
            # links (IDs)
            "project", "tower", "floor", "unit",
            # 🔹 readable names
            "project_name",
            "tower_name",
            "floor_number",
            "unit_no",
            "unit_type_name",
            "configuration_name",
            "facing_name",


                        # NEW pricing fields
            "core_base_price_psf",
            "approved_limit_price_psf",
            "customer_base_price_psf",


            # attributes
            "unit_type", "configuration", "facing",
            "carpet_sqft", "builtup_sqft", "rera_area_sqft",
            "saleable_sqft", "other_area_sqft", "loft_area_sqft",
            "base_price_psf", "rate_psf",
            "agreement_value", "gst_amount",
            "development_infra_charge", "stamp_duty_amount",
            "registration_charges", "legal_fee", "total_cost",
            "unit_status", "status", "availability_status",
            "block_period_days", "registration_number",
            "description", "photo",
            "created_at", "updated_at",
            # nested
            "documents",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "project_name",
            "tower_name",
            "floor_number",
            "unit_no",
            "unit_type_name",
            "configuration_name",
            "facing_name",
        )

    # ------- name helpers (safe if null) -------

    def get_project_name(self, obj):
        return obj.project.name if obj.project_id and obj.project else None

    def get_tower_name(self, obj):
        return obj.tower.name if obj.tower_id and obj.tower else None

    def get_floor_number(self, obj):
        return obj.floor.number if obj.floor_id and obj.floor else None

    def get_unit_no(self, obj):
        return obj.unit.unit_no if obj.unit_id and obj.unit else None

    def get_unit_type_name(self, obj):
        return obj.unit_type.name if obj.unit_type_id and obj.unit_type else None

    def get_configuration_name(self, obj):
        return obj.configuration.name if obj.configuration_id and obj.configuration else None

    def get_facing_name(self, obj):
        return obj.facing.name if obj.facing_id and obj.facing else None

    # ---- your validate / create / update stay same ----
    def validate(self, attrs):
        # ... your existing code ...
        rate = attrs.get("rate_psf", getattr(self.instance, "rate_psf", None))
        agreement_value = attrs.get("agreement_value", getattr(self.instance, "agreement_value", None))
        if rate and not agreement_value:
            area = (
                attrs.get("saleable_sqft", getattr(self.instance, "saleable_sqft", None))
                or attrs.get("rera_area_sqft", getattr(self.instance, "rera_area_sqft", None))
                or attrs.get("carpet_sqft", getattr(self.instance, "carpet_sqft", None))
                or attrs.get("builtup_sqft", getattr(self.instance, "builtup_sqft", None))
            )
            if not area:
                raise serializers.ValidationError(
                    "Provide an area (saleable/rera/carpet/builtup) or set agreement_value when rate_psf is provided."
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        docs = validated_data.pop("documents", [])
        inv = Inventory(**validated_data)
        inv.save()
        if docs:
            for d in docs:
                InventoryDocument.objects.create(inventory=inv, **d)
        return inv

    @transaction.atomic
    def update(self, instance, validated_data):
        docs = validated_data.pop("documents", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if docs is not None:
            InventoryDocument.objects.filter(inventory=instance).delete()
            for d in docs:
                InventoryDocument.objects.create(inventory=instance, **d)
        return instance



class InventoryDocumentReadSerializer(serializers.ModelSerializer):
    doc_type_label = serializers.CharField(
        source="get_doc_type_display",
        read_only=True,
    )

    class Meta:
        model = InventoryDocument
        fields = (
            "id",
            "doc_type",
            "doc_type_label",
            "file",
            "original_name",
        )
        read_only_fields = fields


class InventoryDetailSerializer(serializers.ModelSerializer):
    # --- FK names / labels ---
    project_name = serializers.CharField(
        source="project.name", read_only=True
    )
    tower_name = serializers.CharField(
        source="tower.name", read_only=True
    )
    floor_number = serializers.CharField(
        source="floor.number", read_only=True
    )
    unit_no = serializers.CharField(
        source="unit.unit_no", read_only=True
    )

    unit_type_name = serializers.CharField(
        source="unit_type.name", read_only=True
    )
    configuration_name = serializers.CharField(
        source="configuration.name", read_only=True
    )
    facing_name = serializers.CharField(
        source="facing.name", read_only=True
    )

    # choices → display labels
    unit_status_label = serializers.CharField(
        source="get_unit_status_display", read_only=True
    )
    status_label = serializers.CharField(
        source="get_status_display", read_only=True
    )
    availability_status_label = serializers.CharField(
        source="get_availability_status_display", read_only=True
    )

    documents = InventoryDocumentReadSerializer(many=True, read_only=True)

    class Meta:
        model = Inventory
        # ❗ Notice: NO FK id fields here (project, tower, floor, unit,…)
        fields = (
            "id",

            # Names
            "project_name",
            "tower_name",
            "floor_number",
            "unit_no",
            "unit_type_name",
            "configuration_name",
            "facing_name",

            # Areas
            "carpet_sqft",
            "builtup_sqft",
            "rera_area_sqft",
            "saleable_sqft",
            "other_area_sqft",
            "loft_area_sqft",

            # Pricing & charges
            "base_price_psf",
            "rate_psf",
            "agreement_value",
            "gst_amount",
            "development_infra_charge",
            "stamp_duty_amount",
            "registration_charges",
            "legal_fee",
            "total_cost",



                        # NEW pricing fields
            "core_base_price_psf",
            "approved_limit_price_psf",
            "customer_base_price_psf",


            # Statuses
            "unit_status",
            "unit_status_label",
            "status",
            "status_label",
            "availability_status",
            "availability_status_label",

            # Misc
            "block_period_days",
            "registration_number",
            "description",
            "photo",
            "created_at",
            "updated_at",

            # Docs
            "documents",
        )
        read_only_fields = fields




# clientsetup/serializers_inventory.py

from rest_framework import serializers
from .models import Inventory


class InventoryAvailableUnitSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    tower_name = serializers.CharField(source="tower.name", read_only=True)
    floor_number = serializers.CharField(source="floor.number", read_only=True)
    unit_no = serializers.CharField(source="unit.unit_no", read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id",

            # Relations
            "project",
            "project_name",
            "tower",
            "tower_name",
            "floor",
            "floor_number",
            "unit",
            "unit_no",

            # Config
            "unit_type",
            "configuration",
            "facing",

            # Areas
            "carpet_sqft",
            "builtup_sqft",
            "rera_area_sqft",
            "saleable_sqft",
            "other_area_sqft",
            "loft_area_sqft",

            # Pricing
            "base_price_psf",
            "rate_psf",
            "agreement_value",
            "gst_amount",
            "development_infra_charge",
            "stamp_duty_amount",
            "registration_charges",
            "legal_fee",
            "total_cost",

            # NEW pricing fields
            "core_base_price_psf",
            "approved_limit_price_psf",
            "customer_base_price_psf",

            # Status
            "unit_status",
            "status",
            "availability_status",
        ]
        read_only_fields = [
            "project",
            "tower",
            "floor",
            "unit",
            "total_cost",
        ]


