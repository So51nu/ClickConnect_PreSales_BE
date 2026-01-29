# channel/admin.py
from django.contrib import admin
from .models import (
    AgentType,
    PartnerTier,
    CrmIntegration,
    ChannelPartnerProfile,
    ChannelPartnerProjectAuthorization,
    ChannelPartnerAttachment,
)


@admin.register(AgentType)
class AgentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_by", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)
    raw_id_fields = ("created_by",)


@admin.register(PartnerTier)
class PartnerTierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_global", "is_active", "created_by", "created_at")
    search_fields = ("code", "name")
    list_filter = ("is_global", "is_active")
    raw_id_fields = ("created_by",)


@admin.register(CrmIntegration)
class CrmIntegrationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "auth_type", "is_active", "created_by", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("auth_type", "is_active")
    raw_id_fields = ("created_by",)


@admin.register(ChannelPartnerProfile)
class ChannelPartnerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "get_username",
        "get_full_name",
        "company_name",
        "agent_type",
        "partner_tier",
        "status",
        "onboarding_status",
        "created_by",
        "created_at",
    )
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "company_name",
        "mobile_number",
        "pan_number",
        "gst_in",
        "rera_number",
    )
    list_filter = (
        "status",
        "onboarding_status",
        "agent_type",
        "partner_tier",
        "enable_lead_sharing",
        "regulatory_compliance_approved",
    )
    raw_id_fields = (
        "user",
        "parent_agent",
        "agent_type",
        "partner_tier",
        "crm_integration",
        "created_by",
        "last_modified_by",
    )
    readonly_fields = ("created_at", "updated_at", "last_modified_at")

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = "Username"

    def get_full_name(self, obj):
        return obj.user.get_full_name() or ""
    get_full_name.short_description = "Name"


@admin.register(ChannelPartnerProjectAuthorization)
class ChannelPartnerProjectAuthorizationAdmin(admin.ModelAdmin):
    list_display = (
        "channel_partner",
        "project",
        "status",
        "start_date",
        "end_date",
        "created_by",
        "created_at",
    )
    search_fields = (
        "channel_partner__user__username",
        "channel_partner__user__first_name",
        "channel_partner__user__last_name",
        "project__name",
    )
    list_filter = ("status",)
    raw_id_fields = ("channel_partner", "project", "created_by")


@admin.register(ChannelPartnerAttachment)
class ChannelPartnerAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "channel_partner",
        "file_type",
        "description",
        "created_by",
        "created_at",
    )
    search_fields = (
        "channel_partner__user__username",
        "channel_partner__user__first_name",
        "channel_partner__user__last_name",
        "description",
    )
    list_filter = ("file_type",)
    raw_id_fields = ("channel_partner", "created_by")
