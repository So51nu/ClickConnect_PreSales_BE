from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *
from .views_inventory import InventoryViewSet,InventoryExcelUploadAPIView,InventoryTreeAPIView,AvailableInventoryByProjectAPIView
from .views_excel import ( 
    ProjectExcelUploadAPIView,
    TowerExcelUploadAPIView,
    FloorExcelUploadAPIView,
    UnitExcelUploadAPIView,
        ProjectExcelSampleAPIView,
    TowerExcelSampleAPIView,
    FloorExcelSampleAPIView,
    UnitExcelSampleAPIView,

)
from .views_booking_setup import ProjectBookingSetupAPIView
from .views_parking import ParkingInventoryViewSet, ParkingInventoryTreeAPIView

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"towers", TowerViewSet, basename="tower")
router.register(r"floors", FloorViewSet, basename="floor")
router.register(r"floor-docs", FloorDocumentViewSet, basename="floor-doc")
router.register(r"units", UnitViewSet, basename="unit")
router.register(r"milestone-plans", MilestonePlanViewSet, basename="milestone-plan")
router.register(r"milestone-slabs", MilestoneSlabViewSet, basename="milestone-slab")
router.register(r"payment-plans", PaymentPlanViewSet, basename="payment-plan")
router.register(r"payment-slabs", PaymentSlabViewSet, basename="payment-slab")

router.register(r"banks", BankViewSet, basename="bank")
router.register(r"bank-branches", BankBranchViewSet, basename="bank-branch")
router.register(r"project-banks", ProjectBankViewSet, basename="project-bank")

router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"notification-logs", NotificationDispatchLogViewSet, basename="notification-log")

router.register(r"inventory", InventoryViewSet, basename="inventory")
router.register(r"parking", ParkingInventoryViewSet, basename="parking-inventory")


urlpatterns = [
    path("setup-bundle/", SetupBundleView.as_view(), name="setup-bundle"),
    path("my-scope/", MyScopeView.as_view(), name="my-scope"),
    path("bank-setup/create-all/", CreateBankAllInOneView.as_view(), name="bank-create-all"),
    path("inventory/tree/",InventoryTreeAPIView.as_view(),name="inventory-tree",),

    path("projects/sample-excel/", ProjectExcelSampleAPIView.as_view(), name="project-sample-excel"),
    path("towers/sample-excel/", TowerExcelSampleAPIView.as_view(), name="tower-sample-excel"),
    path("floors/sample-excel/", FloorExcelSampleAPIView.as_view(), name="floor-sample-excel"),
    path("units/sample-excel/", UnitExcelSampleAPIView.as_view(), name="unit-sample-excel"),

    path("inventory/upload-excel/", InventoryExcelUploadAPIView.as_view(), name="inventory-upload-excel"),
    path("projects/upload-excel/", ProjectExcelUploadAPIView.as_view(), name="project-upload-excel"),
    path("towers/upload-excel/", TowerExcelUploadAPIView.as_view(), name="tower-upload-excel"),
    path("floors/upload-excel/", FloorExcelUploadAPIView.as_view(), name="floor-upload-excel"),
    path("units/upload-excel/", UnitExcelUploadAPIView.as_view(), name="unit-upload-excel"),

    path("projects/<int:project_id>/available-units/",AvailableInventoryByProjectAPIView.as_view(),name="project-available-units",),

    path("booking-setup/",ProjectBookingSetupAPIView.as_view(),name="project-booking-setup",),
path("parking/tree/", ParkingInventoryTreeAPIView.as_view(),name="parking-inventory-tree"),
    path("", include(router.urls)),



]
