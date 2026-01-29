from rest_framework import serializers
from .models import BankType, BankCategory, LoanProduct,OfferingType
from setup.models import UnitConfiguration

class BankTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankType
        fields = ["id", "name", "code", "is_active"]



class UnitConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitConfiguration
        fields = [
            "id",
            "name",
            "code",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]


class BankCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BankCategory
        fields = ["id", "name", "code", "is_active"]

class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = ["id", "name", "code", "is_active"]

class OfferingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferingType
        fields = ["id", "name", "code", "is_active"]