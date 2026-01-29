# salelead/admin.py
from django.contrib import admin
from django.conf import settings
from .models import (
    SalesLead,
    SalesLeadAddress,
    SalesLeadUpdate,
    SalesLeadStageHistory,
    SalesLeadDocument,
    LeadComment,
    SiteVisit,
)
from django.contrib import admin

admin.ModelAdmin.search_fields = ("id",)


# -------------------------------------------------------------
# INLINE CLASSES
# -------------------------------------------------------------

class SalesLeadAddressInline(admin.StackedInline):
    model = SalesLeadAddress
    extra = 0
    max_num = 1
    can_delete = True


class SalesLeadUpdateInline(admin.TabularInline):
    model = SalesLeadUpdate
    extra = 0
    fields = ("event_date", "title", "info", "created_by")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-event_date", "-id")


class SalesLeadStageHistoryInline(admin.TabularInline):
    model = SalesLeadStageHistory
    extra = 0
    fields = ("event_date", "stage", "status", "sub_status", "notes", "created_by")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-event_date", "-id")


class SalesLeadDocumentInline(admin.TabularInline):
    model = SalesLeadDocument
    extra = 0
    fields = ("title", "file", "created_at")
    readonly_fields = ("created_at", "updated_at")


# -------------------------------------------------------------
# SALES LEAD ADMIN
# -------------------------------------------------------------
@admin.register(SalesLead)
class SalesLeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "lead_name",
        "mobile_number",
        "email",
        "status",
        "current_owner",
        "assign_to",
        "created_at",
    )

    list_filter = (
        "project",
        "status",
        "sub_status",
        "current_owner",
        "assign_to",
        "created_at",
    )

    search_fields = (
        "first_name",
        "last_name",
        "email",
        "mobile_number",
        "company",
    )

    date_hierarchy = "created_at"
    ordering = ("-id",)

    raw_id_fields = (
        "project",
        "classification",
        "sub_classification",
        "source",
        "sub_source",
        "status",
        "sub_status",
        "purpose",
        "current_owner",
        "assign_to",
        "created_by",
    )

    filter_horizontal = ("offering_types",)

    inlines = [
        SalesLeadAddressInline,
        SalesLeadUpdateInline,
        SalesLeadStageHistoryInline,
        SalesLeadDocumentInline,
    ]

    # FIXED
    def lead_name(self, obj):
        first = obj.first_name or ""
        last = obj.last_name or ""
        full = f"{first} {last}".strip()
        return full or "-"
    lead_name.short_description = "Lead"


# -------------------------------------------------------------
# Lead Comments
# -------------------------------------------------------------
@admin.register(LeadComment)
class LeadCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "sales_lead", "short_text", "stage_at_time", "created_by", "created_at")
    list_filter = ("stage_at_time", "created_at")
    search_fields = ("text", "sales_lead__id")

    def short_text(self, obj):
        return (obj.text[:60] + "…") if len(obj.text) > 60 else obj.text
    short_text.short_description = "Comment"


# -------------------------------------------------------------
# Site Visit Admin
# -------------------------------------------------------------
@admin.register(SiteVisit)
class SiteVisitAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lead_name",
        "project",
        "unit_config",
        "inventory_display",
        "status",
        "scheduled_at",
        "created_by",
        "created_at",
    )

    list_filter = (
        "status",
        "project",
        "unit_config",
        "scheduled_at",
        "created_by",
    )

    search_fields = (
        "lead__first_name",
        "lead__last_name",
        "lead__mobile_number",
        "member_name",
        "member_mobile_number",
    )

    # FIXED — Correct lead full-name
    def lead_name(self, obj):
        if not obj.lead:
            return "-"
        first = obj.lead.first_name or ""
        last = obj.lead.last_name or ""
        return f"{first} {last}".strip()
    lead_name.short_description = "Lead"

    # FIXED — inventory safe references
    def inventory_display(self, obj):
        inv = obj.inventory
        if not inv:
            return "-"

        tower = getattr(inv, "tower", None)
        floor = getattr(inv, "floor", None)
        unit = getattr(inv, "unit", None)

        tower_name = tower.name if tower else "-"
        floor_no = floor.number if floor else "-"
        unit_no = unit.unit_no if unit else "-"

        return f"{tower_name} / {floor_no} / {unit_no}"
    inventory_display.short_description = "Inventory"


from django.contrib import admin
from .models import SalesLeadUpdateStatus

@admin.register(SalesLeadUpdateStatus)
class SalesLeadUpdateStatusAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("code", "label")
    
from django.contrib import admin
from .models import (
    LeadOpportunityStatusConfig,
    LeadOpportunity,
    LeadOpportunityStatusHistory,
)

# --------------------------
# LeadOpportunityStatusConfig
# --------------------------
@admin.register(LeadOpportunityStatusConfig)
class LeadOpportunityStatusConfigAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "code",
        "label",
        "can_convert",
        "is_active",
        "created_by",
    )
    list_filter = ("project", "code", "can_convert", "is_active")

    search_fields = (
        "label",
        "code",
        "project__name",
    )

    autocomplete_fields = ("project", "created_by")
    list_editable = ("can_convert", "is_active")

    def project_name(self, obj):
        if not obj.project:
            return "GLOBAL"
        return (
            getattr(obj.project, "name", None)
            or getattr(obj.project, "name", None)
            or str(obj.project)
        )

    project_name.short_description = "Project"


# --------------------------
# LeadOpportunity
# --------------------------
@admin.register(LeadOpportunity)
class LeadOpportunityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "mobile_number",
        "email",
        "source_system",
        "source_name",
        "project_name",
        "status_code",
        "status_config_label",
        "created_at",
    )
    list_filter = ("source_system", "status", "project")

    search_fields = (
        "full_name",
        "email",
        "mobile_number",
        "external_id",
        "source_name",
        "project__name",
    )

    # In models: FK → project, status_config, created_by
    autocomplete_fields = ("project", "status_config", "created_by")

    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    def project_name(self, obj):
        if not obj.project:
            return "-"
        return (
            getattr(obj.project, "project_name", None)
            or getattr(obj.project, "name", None)
            or str(obj.project)
        )

    project_name.short_description = "Project"

    def status_code(self, obj):
        return obj.status

    status_code.short_description = "Status"

    def status_config_label(self, obj):
        return obj.status_config.label if obj.status_config else ""

    status_config_label.short_description = "Status Config"


# --------------------------
# LeadOpportunityStatusHistory
# --------------------------
@admin.register(LeadOpportunityStatusHistory)
class LeadOpportunityStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "opportunity",
        "old_status_config_label",
        "new_status_config_label",
        "auto_converted",
        "sales_lead",
        "changed_by",
        "created_at",
    )
    list_filter = (
        "auto_converted",
        "old_status_config",
        "new_status_config",
    )
    search_fields = (
        "opportunity__full_name",
        "opportunity__email",
        "opportunity__mobile_number",
        "comment",
        "sales_lead__id",
    )

    # yahan se autocomplete chalega:
    #  - opportunity → LeadOpportunityAdmin (ab search_fields hai)
    #  - old_status_config / new_status_config → LeadOpportunityStatusConfigAdmin (search_fields hai)
    #  - changed_by / sales_lead → unke respective admins
    autocomplete_fields = (
        "opportunity",
        "old_status_config",
        "new_status_config",
        "changed_by",
        "sales_lead",
    )
    date_hierarchy = "created_at"

    def old_status_config_label(self, obj):
        return obj.old_status_config.label if obj.old_status_config else ""

    old_status_config_label.short_description = "Old Config"

    def new_status_config_label(self, obj):
        return obj.new_status_config.label if obj.new_status_config else ""

    new_status_config_label.short_description = "New Config"



from .models import (
    LeadOpportunityAttachment,
)

@admin.register(LeadOpportunityAttachment)
class LeadOpportunityAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "opportunity", "kind", "file", "uploaded_by", "created_at")
    list_filter = ("kind", "uploaded_by")
    search_fields = (
        "file",
        "notes",
        "opportunity__full_name",
        "opportunity__email",
        "opportunity__mobile_number",
    )
    autocomplete_fields = ("opportunity", "uploaded_by")
    date_hierarchy = "created_at"




# salelead/admin.py
from django.contrib import admin
from .models import SalesLead, PaymentLead


@admin.register(PaymentLead)
class PaymentLeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "lead",
        "payment_type",
        "payment_method",
        "amount",
        "status",
        "payment_date",
        "created_by",
    )
    list_filter = (
        "payment_type",
        "payment_method",
        "status",
        "project",
        "payment_date",
    )
    search_fields = (
        "id",
        "lead__first_name",
        "lead__last_name",
        "lead__mobile_number",
        "lead__email",
        "transaction_no",
        "cheque_number",
        "neft_rtgs_ref_no",
        "bank_name",
        "ifsc_code",
    )
    autocomplete_fields = (
        "lead",
        "project",
        "booking",
        "created_by",
    )
    date_hierarchy = "payment_date"
    readonly_fields = ("created_by",)

    fieldsets = (
        ("Basic Payment Info", {
            "fields": (
                "project",
                "lead",
                "booking",
                "payment_type",
                "payment_method",
                "amount",
                "payment_date",
                "status",
                "notes",
            )
        }),
        ("Online / POS", {
            "fields": (
                "payment_mode",
                "transaction_no",
                "pos_slip_image",
            ),
            "classes": ("collapse",),
        }),
        ("Draft / Cheque", {
            "fields": (
                "cheque_number",
                "cheque_date",
                "bank_name",
                "ifsc_code",
                "branch_name",
                "cheque_image",
            ),
            "classes": ("collapse",),
        }),
        ("NEFT / RTGS", {
            "fields": (
                "neft_rtgs_ref_no",
            ),
            "classes": ("collapse",),
        }),
        ("Meta", {
            "fields": ("created_by",),
        }),
    )

    def save_model(self, request, obj, form, change):
        # Admin se create karte time created_by auto set
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# (Optional) agar SalesLead admin already register nahi hai to simple register:
# @admin.register(SalesLead)
# class SalesLeadAdmin(admin.ModelAdmin):
#     pass

