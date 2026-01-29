# clientsetup/serializers_booking_setup.py

from rest_framework import serializers

from .models import (
    Project,
    Tower,
    Floor,
    Unit,
    Inventory,
    PaymentPlan,
    PaymentSlab,
)


class ProjectMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "location", "status", "approval_status", "rera_no","is_pricing_balcony_carpert"]


class InventoryMiniSerializer(serializers.ModelSerializer):
    unit_type_name = serializers.CharField(source="unit_type.name", read_only=True)
    configuration_name = serializers.CharField(source="configuration.name", read_only=True)
    facing_name = serializers.CharField(source="facing.name", read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id",
            "unit_status",
            "availability_status",
            "unit_type_name",
            "configuration_name",
            "facing_name",
            "carpet_sqft",
            "builtup_sqft",
            "rera_area_sqft",
            "balcony_area_sqft",
            "saleable_sqft",
            "base_price_psf",
            "rate_psf",
            "agreement_value",
            "gst_amount",
            "development_infra_charge",
            "stamp_duty_amount",
            "registration_charges",
            "legal_fee",
            "total_cost",
            "approved_limit_price_psf",
        ]


class UnitWithInventorySerializer(serializers.ModelSerializer):
    tower_name = serializers.CharField(source="tower.name", read_only=True)
    floor_number = serializers.CharField(source="floor.number", read_only=True)
    inventory = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            "id",
            "unit_no",
            "status",
            "tower_name",
            "floor_number",
            "agreement_value",  # from Unit model
            "inventory",
        ]

    def get_inventory(self, obj):
        inv = getattr(obj, "inventory_items", None)  # OneToOneField related_name
        if not inv:
            return None
        return InventoryMiniSerializer(inv).data


class FloorWithUnitsSerializer(serializers.ModelSerializer):
    units = UnitWithInventorySerializer(many=True, read_only=True)

    class Meta:
        model = Floor
        fields = ["id", "number", "status", "total_units", "units"]


class TowerWithFloorsSerializer(serializers.ModelSerializer):
    floors = FloorWithUnitsSerializer(many=True, read_only=True)

    class Meta:
        model = Tower
        fields = ["id", "name", "status", "total_floors", "floors"]


class PaymentSlabSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentSlab
        fields = ["id", "order_index", "name", "percentage", "days"]


class PaymentPlanSerializer(serializers.ModelSerializer):
    slabs = PaymentSlabSerializer(many=True, read_only=True)
    total_percentage = serializers.FloatField(read_only=True)

    class Meta:
        model = PaymentPlan
        fields = ["id", "code", "name", "total_percentage", "slabs"]
