# costsheet/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CostSheetTemplateViewSet,
    ProjectCostSheetTemplateViewSet,
    CostSheetTemplateByProjectAPIView,
    CostSheetLeadInitAPIView, 
    ProjectAvailableInventoryAPIView,
    CostSheetCreateAPIView,
        CostSheetViewSet,   
)
router = DefaultRouter()

router.register(r"cost-sheet-templates",CostSheetTemplateViewSet,basename="cost-sheet-template",)
router.register(r"project-cost-sheet-templates",ProjectCostSheetTemplateViewSet,basename="project-cost-sheet-template",)
router.register("cost-sheets", CostSheetViewSet, basename="costsheet") 

urlpatterns = [
    path("cost-sheet-templates/by-project/",CostSheetTemplateByProjectAPIView.as_view(),name="cost-sheet-templates-by-project",),
    path("lead/<int:lead_id>/init/", CostSheetLeadInitAPIView.as_view(),name="costsheet-lead-init"),
    path("available-inventory/", ProjectAvailableInventoryAPIView.as_view(),name="costsheet-available-inventory"),
    path("cost-sheets/all/", CostSheetCreateAPIView.as_view(),name="costsheet-create"),
    path("", include(router.urls)),

]
