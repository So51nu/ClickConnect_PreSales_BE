# leadmanage/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    ProjectLead,
    VisitingHalf,
    FamilySize,
    ResidencyOwnerShip,
    PossienDesigned,
    Occupation,
    Designation,
    NewLeadAssignmentRule,
    LeadBudgetOffer,
    ProjectLeadSiteVisitSetting,
    ProjectLeadReporting,
    LeadSource,
)
from clientsetup.models import Project

User = get_user_model()


# ---------- Basic helpers ----------

class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "full_name"]

    def get_full_name(self, obj):
        fn = (obj.get_full_name() or "").strip()
        return fn or obj.username or obj.email


class LeadSourceMiniSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = LeadSource
        fields = ["id", "name", "project", "project_name"]


class ProjectMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "status", "approval_status"]


# ---------- ProjectLead & children ----------

class ProjectLeadSerializer(serializers.ModelSerializer):
    project = ProjectMiniSerializer(read_only=True)

    class Meta:
        model = ProjectLead
        fields = ["id", "project", "project_description", "logo"]


class NamedLookupSerializerBase(serializers.ModelSerializer):
    """Base for VisitingHalf, FamilySize, etc."""

    class Meta:
        fields = ["id", "name", "is_active", "project_lead"]
        read_only_fields = ["id"]


class VisitingHalfSerializer(NamedLookupSerializerBase):
    class Meta(NamedLookupSerializerBase.Meta):
        model = VisitingHalf


class FamilySizeSerializer(NamedLookupSerializerBase):
    class Meta(NamedLookupSerializerBase.Meta):
        model = FamilySize


class ResidencyOwnerShipSerializer(NamedLookupSerializerBase):
    class Meta(NamedLookupSerializerBase.Meta):
        model = ResidencyOwnerShip


class PossienDesignedSerializer(NamedLookupSerializerBase):
    class Meta(NamedLookupSerializerBase.Meta):
        model = PossienDesigned


class OccupationSerializer(NamedLookupSerializerBase):
    class Meta(NamedLookupSerializerBase.Meta):
        model = Occupation


class DesignationSerializer(NamedLookupSerializerBase):
    class Meta(NamedLookupSerializerBase.Meta):
        model = Designation


# ---------- Budget / Site / Reporting ----------

class LeadBudgetOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadBudgetOffer
        fields = [
            "id",
            "currency",
            "budget_min",
            "budget_max",
            "offering_types",
        ]


class ProjectLeadSiteVisitSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLeadSiteVisitSetting
        fields = [
            "id",
            "enable_scheduled_visits",
            "default_followup_days",
            "notify_channels",
        ]


class ProjectLeadReportingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLeadReporting
        fields = [
            "id",
            "report_type",
            "export_format",
            "frequency",
        ]


# ---------- Assignment rules ----------

class NewLeadAssignmentRuleSerializer(serializers.ModelSerializer):
    project = ProjectMiniSerializer(read_only=True)
    source = LeadSourceMiniSerializer(read_only=True)
    assignees = UserMiniSerializer(many=True, read_only=True)

    class Meta:
        model = NewLeadAssignmentRule
        fields = [
            "id",
            "project_lead",
            "project",
            "source",
            "availability_strategy",
            "is_active",
            "notes",
            "assignees",
            "created_at",
            "updated_at",
        ]


# ---------- FINAL bundle serializer ----------

class LeadSetupBundleSerializer(serializers.Serializer):
    """
    Read-only serializer for the GET bundle:
    all lead-setup related data for a project.
    """

    project = ProjectMiniSerializer(allow_null=True)
    project_lead = ProjectLeadSerializer(allow_null=True)
    visiting_half = VisitingHalfSerializer(many=True)
    family_size = FamilySizeSerializer(many=True)
    residency_ownership = ResidencyOwnerShipSerializer(many=True)
    possession_designed = PossienDesignedSerializer(many=True)
    occupations = OccupationSerializer(many=True)
    designations = DesignationSerializer(many=True)
    budget_offer = LeadBudgetOfferSerializer(allow_null=True)
    site_settings = ProjectLeadSiteVisitSettingSerializer(allow_null=True)
    reporting = ProjectLeadReportingSerializer(allow_null=True)
    assignment_rules = NewLeadAssignmentRuleSerializer(many=True)
