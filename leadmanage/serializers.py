# from django.conf import settings
# from django.db import transaction
# from rest_framework import serializers

# from clientsetup.models import Project
# from setup.models import OfferingType
# from .models import (
#     ProjectLead,
#     LeadBudgetOffer,
#     ProjectLeadSiteVisitSetting,
#     ProjectLeadReporting,
#     LeadSource,
#     LeadClassification,
#     LeadStage,
#     LeadStatus,
#     LeadSubStatus,
#     LeadPurpose,
# )

# # --------- input schemas ---------
# class TreeNodeIn(serializers.Serializer):
#     name = serializers.CharField(max_length=120)
#     order = serializers.IntegerField(required=False)       # used by stages
#     is_closed = serializers.BooleanField(required=False)   # used by statuses (optional)
#     is_won = serializers.BooleanField(required=False)      # used by statuses (optional)
#     children = serializers.ListField(child=serializers.DictField(), required=False)

# class BudgetOfferIn(serializers.Serializer):
#     currency = serializers.CharField()
#     budget_min = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
#     budget_max = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
#     offering_type_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)

# class SiteSettingsIn(serializers.Serializer):
#     enable_scheduled_visits = serializers.BooleanField(default=True)
#     default_followup_days = serializers.IntegerField(default=3)
#     notify_channels = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

# class ReportingIn(serializers.Serializer):
#     report_type = serializers.CharField()
#     export_format = serializers.CharField()
#     frequency = serializers.CharField()

# class ProjectLeadSetupWriteSerializer(serializers.Serializer):
#     """
#     One-shot upsert for a project's lead setup.
#     Works with JSON or multipart (logo file).
#     """
#     project_id = serializers.IntegerField()
#     project_description = serializers.CharField(required=False, allow_blank=True)

#     budget_offer = BudgetOfferIn(required=False)
#     site_settings = SiteSettingsIn(required=False)
#     reporting = ReportingIn(required=False)

#     # trees
#     sources = serializers.ListField(child=TreeNodeIn(), required=False)
#     classifications = serializers.ListField(child=TreeNodeIn(), required=False)

#     # statuses = parents with optional children = sub-statuses
#     statuses = serializers.ListField(child=TreeNodeIn(), required=False)

#     # stages = flat list (order)
#     stages = serializers.ListField(child=TreeNodeIn(), required=False)

#     # purposes = flat list (just names)
#     purposes = serializers.ListField(child=TreeNodeIn(), required=False)

#     logo = serializers.ImageField(required=False, allow_null=True)

#     # ------------ helpers ------------
#     def _admin_id_for(self, user):
#         if getattr(user, "is_staff", False) or getattr(user, "role", None) == "ADMIN":
#             return user.id
#         return getattr(user, "admin_id", None)

#     def _assert_project_ownership(self, project: Project, user):
#         admin_id = self._admin_id_for(user)
#         if not admin_id:
#             raise serializers.ValidationError("No admin context for this user.")
#         if project.belongs_to_id != admin_id:
#             raise serializers.ValidationError("You do not own this project.")

#     # recursive create for LeadSource / LeadClassification (project-scoped)
#     def _rebuild_recursive_per_project(self, model, project: Project, items):
#         model.objects.filter(project=project).delete()
#         created = []

#         def rec(nodes, parent=None):
#             for idx, n in enumerate(nodes or []):
#                 obj = model.objects.create(
#                     project=project,
#                     name=n["name"],
#                     parent=parent if "parent" in [f.name for f in model._meta.fields] else None,
#                 )
#                 created.append(obj)
#                 if n.get("children"):
#                     rec(n["children"], parent=obj)

#         rec(items, None)
#         return created

#     # statuses (LeadStatus + LeadSubStatus)
#     def _rebuild_statuses(self, project: Project, items):
#         LeadSubStatus.objects.filter(status__project=project).delete()
#         LeadStatus.objects.filter(project=project).delete()

#         for n in items or []:
#             status = LeadStatus.objects.create(project=project, name=n["name"])
#             for child in n.get("children", []) or []:
#                 LeadSubStatus.objects.create(status=status, name=child["name"])

#     # purposes (flat)
#     def _rebuild_purposes(self, project: Project, items):
#         LeadPurpose.objects.filter(project=project).delete()
#         if not items:
#             return
#         LeadPurpose.objects.bulk_create(
#             [LeadPurpose(project=project, name=n["name"]) for n in items]
#         )

#     # stages (flat with order)
#     def _rebuild_stages(self, project: Project, items):
#         LeadStage.objects.filter(project=project).delete()
#         bulk = []
#         for idx, n in enumerate(items or []):
#             bulk.append(LeadStage(
#                 project=project,
#                 name=n["name"],
#                 order=n.get("order", idx + 1),
#                 is_closed=n.get("is_closed", False),
#                 is_won=n.get("is_won", False),
#             ))
#         if bulk:
#             LeadStage.objects.bulk_create(bulk)

#     # ------------ create/upsert ------------
#     @transaction.atomic
#     def create(self, validated):
#         request = self.context["request"]
#         project = Project.objects.select_for_update().get(pk=validated["project_id"])
#         self._assert_project_ownership(project, request.user)

#         # upsert header
#         pl, _ = ProjectLead.objects.get_or_create(project=project)
#         if "project_description" in validated:
#             pl.project_description = validated.get("project_description") or ""
#         if "logo" in validated:
#             pl.logo = validated.get("logo")
#         pl.save()

#         # budget/offerings
#         if "budget_offer" in validated:
#             bo_data = validated["budget_offer"]
#             bo, _ = LeadBudgetOffer.objects.get_or_create(project_lead=pl)
#             bo.currency = bo_data["currency"]
#             bo.budget_min = bo_data.get("budget_min")
#             bo.budget_max = bo_data.get("budget_max")
#             bo.save()
#             if "offering_type_ids" in bo_data:
#                 qs = OfferingType.objects.filter(id__in=bo_data["offering_type_ids"])
#                 bo.offering_types.set(qs)

#         # site settings
#         if "site_settings" in validated:
#             ss_data = validated["site_settings"]
#             ss, _ = ProjectLeadSiteVisitSetting.objects.get_or_create(project_lead=pl)
#             ss.enable_scheduled_visits = ss_data.get("enable_scheduled_visits", True)
#             ss.default_followup_days = ss_data.get("default_followup_days", 3)
#             ss.notify_channels = ss_data.get("notify_channels", [])
#             ss.save()

#         # reporting
#         if "reporting" in validated:
#             rp_data = validated["reporting"]
#             rp, _ = ProjectLeadReporting.objects.get_or_create(project_lead=pl)
#             rp.report_type = rp_data["report_type"]
#             rp.export_format = rp_data["export_format"]
#             rp.frequency = rp_data["frequency"]
#             rp.save()

#         # trees & lists (project-scoped)
#         if "sources" in validated:
#             self._rebuild_recursive_per_project(LeadSource, project, validated["sources"])
#         if "classifications" in validated:
#             self._rebuild_recursive_per_project(LeadClassification, project, validated["classifications"])
#         if "statuses" in validated:
#             self._rebuild_statuses(project, validated["statuses"])
#         if "purposes" in validated:
#             self._rebuild_purposes(project, validated["purposes"])
#         if "stages" in validated:
#             self._rebuild_stages(project, validated["stages"])

#         return {"project_lead_id": pl.id}

#     def update(self, instance, validated_data):
#         raise NotImplementedError("Use POST for idempotent upsert by project_id.")



# from rest_framework import serializers
# from .models import (
#     ProjectLead,
#     LeadBudgetOffer,
#     ProjectLeadSiteVisitSetting,
#     ProjectLeadReporting,
#     LeadClassification,
#     LeadSource,
#     LeadStage,
#     LeadStatus,
#     LeadSubStatus,
#     LeadPurpose,
# )
# from setup.models import OfferingType


# class LeadBudgetOfferSerializer(serializers.ModelSerializer):
#     offering_types = serializers.PrimaryKeyRelatedField(
#         many=True, required=False, queryset=OfferingType.objects.all()
#     )

#     class Meta:
#         model = LeadBudgetOffer
#         fields = ["currency", "budget_min", "budget_max", "offering_types"]

#     def create(self, validated):
#         offering_types = validated.pop("offering_types", [])
#         obj = LeadBudgetOffer.objects.create(**validated)
#         if offering_types:
#             obj.offering_types.set(offering_types)
#         return obj

#     def update(self, instance, validated):
#         offering_types = validated.pop("offering_types", None)
#         obj = super().update(instance, validated)
#         if offering_types is not None:
#             obj.offering_types.set(offering_types)
#         return obj


# class ProjectLeadSiteVisitSettingSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ProjectLeadSiteVisitSetting
#         fields = ["enable_scheduled_visits", "default_followup_days", "notify_channels"]


# class ProjectLeadReportingSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = ProjectLeadReporting
#         fields = ["report_type", "export_format", "frequency"]


# class ProjectLeadSerializer(serializers.ModelSerializer):
#     # child one-to-ones
#     budget_offer = LeadBudgetOfferSerializer(required=False)
#     site_settings = ProjectLeadSiteVisitSettingSerializer(required=False)
#     reporting = ProjectLeadReportingSerializer(required=False)

#     class Meta:
#         model = ProjectLead
#         fields = [
#             "id",
#             "project",                 # pass project id for upsert (write-only effectively)
#             "project_description",
#             "logo",
#             "budget_offer",
#             "site_settings",
#             "reporting",
#             "created_at",
#             "updated_at",
#         ]
#         read_only_fields = ["created_at", "updated_at"]

#     def create(self, validated):
#         # Create header first, then upsert children
#         budget_offer = validated.pop("budget_offer", None)
#         site_settings = validated.pop("site_settings", None)
#         reporting = validated.pop("reporting", None)

#         pl = ProjectLead.objects.create(**validated)

#         if budget_offer is not None:
#             self.fields["budget_offer"].create({**budget_offer, "project_lead": pl})
#         if site_settings is not None:
#             ProjectLeadSiteVisitSetting.objects.create(project_lead=pl, **site_settings)
#         if reporting is not None:
#             ProjectLeadReporting.objects.create(project_lead=pl, **reporting)

#         return pl

#     def update(self, instance, validated):
#         budget_offer = validated.pop("budget_offer", None)
#         site_settings = validated.pop("site_settings", None)
#         reporting = validated.pop("reporting", None)

#         # update header
#         for k, v in validated.items():
#             setattr(instance, k, v)
#         instance.save()

#         # upsert children
#         if budget_offer is not None:
#             if hasattr(instance, "budget_offer"):
#                 self.fields["budget_offer"].update(instance.budget_offer, budget_offer)
#             else:
#                 self.fields["budget_offer"].create({**budget_offer, "project_lead": instance})

#         if site_settings is not None:
#             if hasattr(instance, "site_settings"):
#                 for k, v in site_settings.items():
#                     setattr(instance.site_settings, k, v)
#                 instance.site_settings.save()
#             else:
#                 ProjectLeadSiteVisitSetting.objects.create(project_lead=instance, **site_settings)

#         if reporting is not None:
#             if hasattr(instance, "reporting"):
#                 for k, v in reporting.items():
#                     setattr(instance.reporting, k, v)
#                 instance.reporting.save()
#             else:
#                 ProjectLeadReporting.objects.create(project_lead=instance, **reporting)

#         return instance


# # Lightweight serializers for masters (read-only for detail endpoint)
# class _IdNameSerializer(serializers.ModelSerializer):
#     class Meta:
#         fields = ["id", "name"]


# class LeadClassificationSerializer(_IdNameSerializer):
#     class Meta(_IdNameSerializer.Meta):
#         model = LeadClassification


# class LeadSourceSerializer(_IdNameSerializer):
#     class Meta(_IdNameSerializer.Meta):
#         model = LeadSource


# class LeadStageSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = LeadStage
#         fields = ["id", "name", "order", "is_closed", "is_won"]


# class LeadSubStatusSerializer(_IdNameSerializer):
#     class Meta(_IdNameSerializer.Meta):
#         model = LeadSubStatus


# class LeadStatusWithSubsSerializer(serializers.ModelSerializer):
#     sub_statuses = LeadSubStatusSerializer(many=True, read_only=True)

#     class Meta:
#         model = LeadStatus
#         fields = ["id", "name", "sub_statuses"]


# class LeadPurposeSerializer(_IdNameSerializer):
#     class Meta(_IdNameSerializer.Meta):
#         model = LeadPurpose



from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import (
    LeadClassification, LeadSource, LeadStage, LeadStatus, LeadSubStatus,
    LeadPurpose, ProjectLead, NewLeadAssignmentRule, LeadBudgetOffer,
    ProjectLeadSiteVisitSetting, ProjectLeadReporting, AvailabilityStrategy
)
from setup.models import OfferingType  # adjust import if your app label differs

User = get_user_model()


# serializers.py
from rest_framework import serializers
from .models import LeadStage

class LeadStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadStage
        fields = ["id", "project", "name", "order", "is_closed", "is_won", "created_at", "updated_at"]

    def validate(self, attrs):
        project = attrs.get("project") or getattr(self.instance, "project", None)
        if project:
            qs = LeadStage.objects.filter(project=project)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.count() >= 8:
                raise serializers.ValidationError("Only 8 lead stages are allowed per project.")
        return attrs


class LeadPurposeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadPurpose
        fields = ["id", "project", "name", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class LeadClassificationTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = LeadClassification
        fields = ["id", "project", "name", "parent", "children"]

    def get_children(self, obj):
        qs = obj.children.all().order_by("name")
        return LeadClassificationTreeSerializer(qs, many=True).data


class LeadSourceTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = LeadSource
        fields = ["id", "project", "name", "parent", "children","for_cp"]

    def get_children(self, obj):
        qs = obj.children.all().order_by("name")
        return LeadSourceTreeSerializer(qs, many=True).data




class OfferingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferingType
        fields = ["id", "name"]

# -------- Status + SubStatus --------
class LeadSubStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadSubStatus
        fields = ["id", "status", "name", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class LeadStatusWithSubsSerializer(serializers.ModelSerializer):
    sub_statuses = LeadSubStatusSerializer(many=True, read_only=True)

    class Meta:
        model = LeadStatus
        fields = ["id", "project", "name", "sub_statuses", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class ProjectLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLead
        fields = ["id", "project", "project_description", "logo", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class LeadBudgetOfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadBudgetOffer
        fields = [
            "id", "project_lead",
            "currency", "budget_min", "budget_max", "offering_types",
            "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at"]


class ProjectLeadSiteVisitSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLeadSiteVisitSetting
        fields = [
            "id", "project_lead",
            "enable_scheduled_visits", "default_followup_days", "notify_channels",
            "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at"]


class ProjectLeadReportingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLeadReporting
        fields = [
            "id", "project_lead",
            "report_type", "export_format", "frequency",
            "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at"]


class NewLeadAssignmentRuleSerializer(serializers.ModelSerializer):
    assignees = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=False
    )
    availability_strategy = serializers.ChoiceField(
        choices=AvailabilityStrategy.choices, default=AvailabilityStrategy.ROUND_ROBIN
    )

    class Meta:
        model = NewLeadAssignmentRule
        fields = [
            "id", "project_lead", "project", "source",
            "assignees", "availability_strategy", "is_active", "notes",
            "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at"]



class ProjectLeadSetupWriteSerializer(serializers.Serializer):
    """
    Payload:
    {
      "project": <id>,                              # required
      "project_lead": {"project_description": "...", "logo": <optional file>},
      "budget_offer": {"currency":"INR","budget_min":..., "budget_max":..., "offering_types":[ids]},
      "site_settings": {"enable_scheduled_visits":true,"default_followup_days":3,"notify_channels":["EMAIL"]},
      "reporting": {"report_type":"SUMMARY","export_format":"CSV","frequency":"WEEKLY"},
      "assignment_rules": [
        {"project": <id or null>, "source": <id or null>,
         "assignees":[user_ids], "availability_strategy":"ROUND_ROBIN", "is_active":true, "notes":""}
      ]
    }
    """
    project = serializers.IntegerField()
    project_lead = serializers.DictField(required=False)
    budget_offer = serializers.DictField(required=False)
    site_settings = serializers.DictField(required=False)
    reporting = serializers.DictField(required=False)
    assignment_rules = serializers.ListField(child=serializers.DictField(), required=False)

    def validate(self, data):
        if not data.get("project"):
            raise serializers.ValidationError("project is required.")
        return data

    @transaction.atomic
    def create(self, validated):
        project_id = validated["project"]

        # upsert ProjectLead
        pl, _ = ProjectLead.objects.get_or_create(project_id=project_id)
        pl_data = validated.get("project_lead") or {}
        if "project_description" in pl_data:
            pl.project_description = pl_data["project_description"]
        if "logo" in pl_data:
            pl.logo = pl_data["logo"]
        pl.save()

        # upsert Budget
        bo_data = validated.get("budget_offer")
        if bo_data is not None:
            bo, _ = LeadBudgetOffer.objects.get_or_create(project_lead=pl)
            for k in ["currency", "budget_min", "budget_max"]:
                if k in bo_data:
                    setattr(bo, k, bo_data[k])
            bo.save()
            if "offering_types" in bo_data:
                bo.offering_types.set(bo_data["offering_types"])

        # upsert Site Settings
        ss_data = validated.get("site_settings")
        if ss_data is not None:
            ss, _ = ProjectLeadSiteVisitSetting.objects.get_or_create(project_lead=pl)
            for k in ["enable_scheduled_visits", "default_followup_days", "notify_channels"]:
                if k in ss_data:
                    setattr(ss, k, ss_data[k])
            ss.save()

        # upsert Reporting
        rp_data = validated.get("reporting")
        if rp_data is not None:
            rp, _ = ProjectLeadReporting.objects.get_or_create(project_lead=pl)
            for k in ["report_type", "export_format", "frequency"]:
                if k in rp_data:
                    setattr(rp, k, rp_data[k])
            rp.save()

        # Reset & recreate assignment rules if provided
        ar_list = validated.get("assignment_rules")
        if ar_list is not None:
            NewLeadAssignmentRule.objects.filter(project_lead=pl).delete()
            for item in ar_list:
                assignees = item.pop("assignees", [])
                rule = NewLeadAssignmentRule.objects.create(project_lead=pl, **item)
                if assignees:
                    rule.assignees.set(assignees)

        # Return a compact read model
        return {
            "project_lead": ProjectLeadSerializer(pl).data,
            "budget_offer": LeadBudgetOfferSerializer(getattr(pl, "budget_offer", None)).data if hasattr(pl, "budget_offer") else None,
            "site_settings": ProjectLeadSiteVisitSettingSerializer(getattr(pl, "site_settings", None)).data if hasattr(pl, "site_settings") else None,
            "reporting": ProjectLeadReportingSerializer(getattr(pl, "reporting", None)).data if hasattr(pl, "reporting") else None,
            "assignment_rules": NewLeadAssignmentRuleSerializer(
                NewLeadAssignmentRule.objects.filter(project_lead=pl), many=True
            ).data
        }

    def to_representation(self, instance):
        # instance is the dict returned from create()
        return instance


from rest_framework import serializers
from .models import (
    VisitingHalf,
    FamilySize,
    ResidencyOwnerShip,
    PossienDesigned,
    Occupation,
    Designation,
)

# Assume NamedLookup already has fields: id, name, code, is_active, etc.

class ProjectLeadLookupBaseSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ["id", "project_lead", "name", "code", "is_active"]
        read_only_fields = ["id"]


class VisitingHalfSerializer(ProjectLeadLookupBaseSerializer):
    class Meta(ProjectLeadLookupBaseSerializer.Meta):
        model = VisitingHalf


class FamilySizeSerializer(ProjectLeadLookupBaseSerializer):
    class Meta(ProjectLeadLookupBaseSerializer.Meta):
        model = FamilySize


class ResidencyOwnerShipSerializer(ProjectLeadLookupBaseSerializer):
    class Meta(ProjectLeadLookupBaseSerializer.Meta):
        model = ResidencyOwnerShip


class PossienDesignedSerializer(ProjectLeadLookupBaseSerializer):
    class Meta(ProjectLeadLookupBaseSerializer.Meta):
        model = PossienDesigned


class OccupationSerializer(ProjectLeadLookupBaseSerializer):
    class Meta(ProjectLeadLookupBaseSerializer.Meta):
        model = Occupation


class DesignationSerializer(ProjectLeadLookupBaseSerializer):
    class Meta(ProjectLeadLookupBaseSerializer.Meta):
        model = Designation





