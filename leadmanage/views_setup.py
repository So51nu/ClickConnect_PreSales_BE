# leadmanage/views_setup.py  (or add into your views.py)

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from clientsetup.models import Project
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
)
from .serializers_setup import (
    LeadSetupBundleSerializer,
    VisitingHalfSerializer,
    FamilySizeSerializer,
    ResidencyOwnerShipSerializer,
    PossienDesignedSerializer,
    OccupationSerializer,
    DesignationSerializer,
    ProjectLeadSerializer,
    LeadBudgetOfferSerializer,
    ProjectLeadSiteVisitSettingSerializer,
    ProjectLeadReportingSerializer,
    NewLeadAssignmentRuleSerializer,
    ProjectMiniSerializer,
)


class LeadSetupByProjectView(APIView):
    """
    GET /api/leadManagement/lead-setup-by-project/?project_id=3

    Returns:
    {
      "project": {...},
      "project_lead": {...} | null,
      "visiting_half": [...],
      "family_size": [...],
      "residency_ownership": [...],
      "possession_designed": [...],
      "occupations": [...],
      "designations": [...],
      "budget_offer": {...} | null,
      "site_settings": {...} | null,
      "reporting": {...} | null,
      "assignment_rules": [...]
    }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        project_id = request.query_params.get("project_id")

        if not project_id:
            return Response(
                {"detail": "project_id query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Project must exist
        project = get_object_or_404(Project, pk=project_id)

        # ProjectLead is OneToOne; may or may not exist
        try:
          # related_name="lead_setup"
          project_lead = project.lead_setup
        except ProjectLead.DoesNotExist:
          project_lead = None

        # If we have a project_lead, use it to filter children
        if project_lead:
            vh_qs = VisitingHalf.objects.filter(project_lead=project_lead)
            fs_qs = FamilySize.objects.filter(project_lead=project_lead)
            ro_qs = ResidencyOwnerShip.objects.filter(project_lead=project_lead)
            pd_qs = PossienDesigned.objects.filter(project_lead=project_lead)
            oc_qs = Occupation.objects.filter(project_lead=project_lead)
            dg_qs = Designation.objects.filter(project_lead=project_lead)

            budget_offer = getattr(project_lead, "budget_offer", None)
            site_settings = getattr(project_lead, "site_settings", None)
            reporting = getattr(project_lead, "reporting", None)

            assignment_rules_qs = NewLeadAssignmentRule.objects.filter(
                project_lead=project_lead
            ).select_related("project", "source").prefetch_related("assignees")
        else:
            vh_qs = VisitingHalf.objects.none()
            fs_qs = FamilySize.objects.none()
            ro_qs = ResidencyOwnerShip.objects.none()
            pd_qs = PossienDesigned.objects.none()
            oc_qs = Occupation.objects.none()
            dg_qs = Designation.objects.none()

            budget_offer = None
            site_settings = None
            reporting = None
            assignment_rules_qs = NewLeadAssignmentRule.objects.none()

        # Build response data
        payload = {
            "project": ProjectMiniSerializer(project).data,
            "project_lead": ProjectLeadSerializer(project_lead).data if project_lead else None,
            "visiting_half": VisitingHalfSerializer(vh_qs, many=True).data,
            "family_size": FamilySizeSerializer(fs_qs, many=True).data,
            "residency_ownership": ResidencyOwnerShipSerializer(ro_qs, many=True).data,
            "possession_designed": PossienDesignedSerializer(pd_qs, many=True).data,
            "occupations": OccupationSerializer(oc_qs, many=True).data,
            "designations": DesignationSerializer(dg_qs, many=True).data,
            "budget_offer": LeadBudgetOfferSerializer(budget_offer).data if budget_offer else None,
            "site_settings": ProjectLeadSiteVisitSettingSerializer(site_settings).data if site_settings else None,
            "reporting": ProjectLeadReportingSerializer(reporting).data if reporting else None,
            "assignment_rules": NewLeadAssignmentRuleSerializer(
                assignment_rules_qs, many=True
            ).data,
        }

        # You *could* run it through LeadSetupBundleSerializer(payload),
        # but since it's read-only, simply return payload is fine
        return Response(payload, status=status.HTTP_200_OK)
