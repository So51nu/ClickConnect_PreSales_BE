# leadmanage/admin.py
from django.contrib import admin
from .models import (
    LeadClassification,
    LeadSource,
    LeadStage,
    LeadStatus,
    LeadSubStatus,
    LeadPurpose,
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
)


# ------------------ BASIC MASTER ADMINS ------------------ #

@admin.register(LeadClassification)
class LeadClassificationAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "name", "parent")
    list_filter = ("project", "parent")
    search_fields = ("name", "project__name")
    raw_id_fields = ("project", "parent")
    ordering = ("project__name", "parent__id", "name")


@admin.register(LeadSource)
class LeadSourceAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "name", "parent")
    list_filter = ("project", "parent")
    search_fields = ("name", "project__name")
    raw_id_fields = ("project", "parent")
    ordering = ("project__name", "parent__id", "name")


@admin.register(LeadStage)
class LeadStageAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "order", "name", "is_closed", "is_won")
    list_filter = ("project", "is_closed", "is_won")
    search_fields = ("name", "project__name")
    raw_id_fields = ("project",)
    ordering = ("project__name", "order")


@admin.register(LeadStatus)
class LeadStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "name")
    list_filter = ("project",)
    search_fields = ("name", "project__name")
    raw_id_fields = ("project",)
    ordering = ("project__name", "name")


@admin.register(LeadSubStatus)
class LeadSubStatusAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "name")
    list_filter = ("status__project", "status")
    search_fields = ("name", "status__name", "status__project__name")
    raw_id_fields = ("status",)
    ordering = ("status__project__name", "status__name", "name")


@admin.register(LeadPurpose)
class LeadPurposeAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "name")
    list_filter = ("project",)
    search_fields = ("name", "project__name")
    raw_id_fields = ("project",)
    ordering = ("project__name", "name")


# ------------------ INLINE CONFIGS FOR PROJECTLEAD ------------------ #

class LeadBudgetOfferInline(admin.StackedInline):
    model = LeadBudgetOffer
    extra = 0
    raw_id_fields = ("project_lead",)
    filter_horizontal = ("offering_types",)


class ProjectLeadSiteVisitSettingInline(admin.StackedInline):
    model = ProjectLeadSiteVisitSetting
    extra = 0
    raw_id_fields = ("project_lead",)


class ProjectLeadReportingInline(admin.StackedInline):
    model = ProjectLeadReporting
    extra = 0
    raw_id_fields = ("project_lead",)


class NewLeadAssignmentRuleInline(admin.TabularInline):
    model = NewLeadAssignmentRule
    extra = 0
    raw_id_fields = ("project_lead", "project", "source", "assignees")
    filter_horizontal = ("assignees",)


class VisitingHalfInline(admin.TabularInline):
    model = VisitingHalf
    extra = 0
    raw_id_fields = ("project_lead",)


class FamilySizeInline(admin.TabularInline):
    model = FamilySize
    extra = 0
    raw_id_fields = ("project_lead",)


class ResidencyOwnerShipInline(admin.TabularInline):
    model = ResidencyOwnerShip
    extra = 0
    raw_id_fields = ("project_lead",)


class PossienDesignedInline(admin.TabularInline):
    model = PossienDesigned
    extra = 0
    raw_id_fields = ("project_lead",)


class OccupationInline(admin.TabularInline):
    model = Occupation
    extra = 0
    raw_id_fields = ("project_lead",)


class DesignationInline(admin.TabularInline):
    model = Designation
    extra = 0
    raw_id_fields = ("project_lead",)


# ------------------ PROJECTLEAD ADMIN (MAIN HUB) ------------------ #

@admin.register(ProjectLead)
class ProjectLeadAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "short_description", "created_at", "updated_at")
    search_fields = ("project__name",)
    raw_id_fields = ("project",)
    ordering = ("project__name",)

    inlines = [
        LeadBudgetOfferInline,
        ProjectLeadSiteVisitSettingInline,
        ProjectLeadReportingInline,
        NewLeadAssignmentRuleInline,
        VisitingHalfInline,
        FamilySizeInline,
        ResidencyOwnerShipInline,
        PossienDesignedInline,
        OccupationInline,
        DesignationInline,
    ]

    def short_description(self, obj):
        if not obj.project_description:
            return ""
        if len(obj.project_description) <= 60:
            return obj.project_description
        return obj.project_description[:57] + "..."
    short_description.short_description = "Project Description"


# ------------------ STANDALONE ADMINS FOR RULES & CONFIGS ------------------ #

@admin.register(NewLeadAssignmentRule)
class NewLeadAssignmentRuleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project_lead",
        "project",
        "source",
        "availability_strategy",
        "is_active",
        "created_at",
    )
    list_filter = (
        "availability_strategy",
        "is_active",
        "project_lead__project",
        "project",
        "source",
    )
    search_fields = (
        "project_lead__project__name",
        "project__name",
        "source__name",
        "notes",
    )
    raw_id_fields = ("project_lead", "project", "source", "assignees")
    filter_horizontal = ("assignees",)
    ordering = ("-created_at",)


@admin.register(LeadBudgetOffer)
class LeadBudgetOfferAdmin(admin.ModelAdmin):
    list_display = ("id", "project_lead", "currency", "budget_min", "budget_max")
    list_filter = ("currency",)
    search_fields = (
        "project_lead__project__name",
    )
    raw_id_fields = ("project_lead",)
    filter_horizontal = ("offering_types",)


@admin.register(ProjectLeadSiteVisitSetting)
class ProjectLeadSiteVisitSettingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project_lead",
        "enable_scheduled_visits",
        "default_followup_days",
    )
    list_filter = ("enable_scheduled_visits",)
    raw_id_fields = ("project_lead",)
    search_fields = ("project_lead__project__name",)


@admin.register(ProjectLeadReporting)
class ProjectLeadReportingAdmin(admin.ModelAdmin):
    list_display = ("id", "project_lead", "report_type", "export_format", "frequency")
    list_filter = ("report_type", "export_format", "frequency")
    raw_id_fields = ("project_lead",)
    search_fields = ("project_lead__project__name",)


# ------------------ OPTIONAL: DIRECT ADMINS FOR NAMEDLOOKUP VARIANTS ------------------ #

@admin.register(VisitingHalf)
class VisitingHalfAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project_lead")
    list_filter = ("project_lead",)
    search_fields = ("name", "project_lead__project__name")
    raw_id_fields = ("project_lead",)


@admin.register(FamilySize)
class FamilySizeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project_lead")
    list_filter = ("project_lead",)
    search_fields = ("name", "project_lead__project__name")
    raw_id_fields = ("project_lead",)


@admin.register(ResidencyOwnerShip)
class ResidencyOwnerShipAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project_lead")
    list_filter = ("project_lead",)
    search_fields = ("name", "project_lead__project__name")
    raw_id_fields = ("project_lead",)


@admin.register(PossienDesigned)
class PossienDesignedAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project_lead")
    list_filter = ("project_lead",)
    search_fields = ("name", "project_lead__project__name")
    raw_id_fields = ("project_lead",)


@admin.register(Occupation)
class OccupationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project_lead")
    list_filter = ("project_lead",)
    search_fields = ("name", "project_lead__project__name")
    raw_id_fields = ("project_lead",)


@admin.register(Designation)
class DesignationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "project_lead")
    list_filter = ("project_lead",)
    search_fields = ("name", "project_lead__project__name")
    raw_id_fields = ("project_lead",)
