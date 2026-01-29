# clientsetup/serializers_parking.py (ya jaha tum rakhna chaho)
from rest_framework import serializers
from .models import ParkingInventory


class ParkingInventorySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    tower_name = serializers.CharField(source="tower.name", read_only=True)
    reserved_unit_no = serializers.CharField(
        source="reserved_for_unit.unit_no", read_only=True
    )

    class Meta:
        model = ParkingInventory
        fields = [
            "id",

            # FK ids
            "project",
            "tower",
            "reserved_for_unit",

            # FK display
            "project_name",
            "tower_name",
            "reserved_unit_no",

            # Parking identity
            "slot_label",
            "rera_slot_no",
            "parking_type",
            "level_label",
            "area_sqft",

            # Status
            "status",
            "availability_status",
            "blocked_until",
            "remarks",

            "created_at",
            "updated_at",
        ]
        read_only_fields = ["blocked_until", "created_at", "updated_at"]


class ParkingInventoryDetailSerializer(ParkingInventorySerializer):
    """
    If you want to add history / logs later, yahin extend kar sakte ho.
    """
    class Meta(ParkingInventorySerializer.Meta):
        fields = ParkingInventorySerializer.Meta.fields + []

