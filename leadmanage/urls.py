# from django.urls import path
# from .views import (
#     ProjectLeadSetupUpsertAPIView,
#     ProjectLeadSetupDetailAPIView,
#     MyProjectLeadsListAPIView,
# )


# urlpatterns = [
#     path("leadsetup/upsert/", ProjectLeadSetupUpsertAPIView.as_view(), name="leadsetup-upsert"),

#     path("leadsetup/detail/", ProjectLeadSetupDetailAPIView.as_view(), name="leadsetup-detail"),

#     path("leadsetup/my-projects/", MyProjectLeadsListAPIView.as_view(), name="leadsetup-my-projects"),
# ]


from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LeadMastersAPIView,
    LeadClassificationViewSet, LeadSourceViewSet, LeadStageViewSet,
    LeadStatusViewSet, LeadSubStatusViewSet, LeadPurposeViewSet,
    ProjectLeadViewSet, LeadBudgetOfferViewSet, ProjectLeadSiteVisitSettingViewSet,
    ProjectLeadReportingViewSet, NewLeadAssignmentRuleViewSet,
    ProjectLeadSetupUpsertAPIView,
)
from .views_setup import LeadSetupByProjectView 
from .views_extra_lookups import (
    VisitingHalfViewSet,
    FamilySizeViewSet,
    ResidencyOwnerShipViewSet,
    PossienDesignedViewSet,
    OccupationViewSet,
    DesignationViewSet,
)


router = DefaultRouter()
router.register(r"classifications", LeadClassificationViewSet, basename="lead-classification")
router.register(r"sources", LeadSourceViewSet, basename="lead-source")
router.register(r"stages", LeadStageViewSet, basename="lead-stage")
router.register(r"statuses", LeadStatusViewSet, basename="lead-status")
router.register(r"sub-statuses", LeadSubStatusViewSet, basename="lead-sub-status")
router.register(r"purposes", LeadPurposeViewSet, basename="lead-purpose")

router.register(r"project-lead", ProjectLeadViewSet, basename="project-lead")
router.register(r"budget-offer", LeadBudgetOfferViewSet, basename="lead-budget-offer")
router.register(r"site-settings", ProjectLeadSiteVisitSettingViewSet, basename="lead-site-settings")
router.register(r"reporting", ProjectLeadReportingViewSet, basename="lead-reporting")
router.register(r"assignment-rules", NewLeadAssignmentRuleViewSet, basename="lead-assignment-rule")

router.register(r"visiting-half", VisitingHalfViewSet, basename="visiting-half")
router.register(r"family-size", FamilySizeViewSet, basename="family-size")
router.register(r"residency-ownership", ResidencyOwnerShipViewSet, basename="residency-ownership")
router.register(r"possession-designed", PossienDesignedViewSet, basename="possession-designed")
router.register(r"occupations", OccupationViewSet, basename="occupation")
router.register(r"designations", DesignationViewSet, basename="designation")

urlpatterns = [
    path("v2/leads/masters/", LeadMastersAPIView.as_view(), name="lead-masters"),
    path("v2/leads/setup/", ProjectLeadSetupUpsertAPIView.as_view(), name="lead-setup-upsert"),
    path(
        "lead-setup-by-project/",
        LeadSetupByProjectView.as_view(),
        name="lead-setup-by-project",
    ),
    path("", include(router.urls)),


]