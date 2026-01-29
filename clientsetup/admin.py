from django.contrib import admin
from .models import (
    Project, Tower, Floor, FloorDocument, Unit,
    MilestonePlan, MilestoneSlab,Inventory,InventoryDocument,PaymentPlan,PaymentSlab
,InventoryStatusHistory
)
admin.site.register([Project,InventoryStatusHistory, Tower, Floor, FloorDocument, Unit, MilestonePlan, MilestoneSlab,InventoryDocument,PaymentPlan,PaymentSlab])

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "tower", "unit", "unit_type", "availability_status", "status", "total_cost")
    list_filter = ("project", "tower", "availability_status", "status", "unit_type")
    search_fields = ("registration_number",)
    readonly_fields = ("total_cost",)
