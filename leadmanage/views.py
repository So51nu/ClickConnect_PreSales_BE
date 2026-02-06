
from setup.models import UnitConfiguration
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets, status
from rest_framework.response import Response
from rest_framework.views import APIView
# views.py
from setup.models import OfferingType 
from .models import (
    LeadClassification, LeadSource, LeadStage, LeadStatus, LeadSubStatus,
    LeadPurpose, ProjectLead, NewLeadAssignmentRule, LeadBudgetOffer,
    ProjectLeadSiteVisitSetting, ProjectLeadReporting
)
from .serializers import (
    LeadClassificationTreeSerializer, LeadSourceTreeSerializer,
    LeadStatusWithSubsSerializer, LeadSubStatusSerializer,
    LeadStageSerializer, LeadPurposeSerializer,
    ProjectLeadSerializer, NewLeadAssignmentRuleSerializer,
    LeadBudgetOfferSerializer, ProjectLeadSiteVisitSettingSerializer,
    ProjectLeadReportingSerializer, ProjectLeadSetupWriteSerializer,OfferingTypeSerializer
)
from accounts.models import User
from setup.serializers import  UnitConfigurationSerializer
from common.tenancy import assert_project_allowed
from salelead.utils import _project_ids_for_user

class IsAuth(permissions.IsAuthenticated):
    pass



def admin_context_id(user):
    """
    Decide which 'admin' bucket this user belongs to.

    - If super-admin / staff / role=ADMIN -> treat user itself as admin.
    - Else -> use user.admin_id (FK to admin user).
    """
    if getattr(user, "is_staff", False) or getattr(user, "role", None) == "ADMIN":
        return user.id
    return getattr(user, "admin_id", None)


class LeadMastersAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "project_id is required."}, status=400)
        assert_project_allowed(request, project_id)

        # ---------------------------
        # Project-scoped masters
        # ---------------------------
        classifications = LeadClassification.objects.filter(
            project_id=project_id, parent__isnull=True
        ).order_by("name")

        sources = LeadSource.objects.filter(
            project_id=project_id, parent__isnull=True
        ).order_by("name")

        stages = LeadStage.objects.filter(project_id=project_id).order_by(
            "order", "name"
        )
        purposes = LeadPurpose.objects.filter(project_id=project_id).order_by("name")

        statuses = LeadStatus.objects.filter(project_id=project_id).prefetch_related(
            Prefetch("sub_statuses", queryset=LeadSubStatus.objects.order_by("name"))
        ).order_by("name")

        # 🔹 Unit configurations for this project (2BHK / 3BHK / etc.)
        unit_configurations = UnitConfiguration.objects.filter(
            is_active=True
        ).order_by("name")

        # Global (not project-scoped) — send all OfferingType
        offering_types = OfferingType.objects.all().order_by("name")

        # ---------------------------
        # Assign-to users (same admin context)
        # ---------------------------
        admin_id = admin_context_id(request.user)
        assign_qs = User.objects.none()

        if admin_id:
            # all active users under same admin
            assign_qs = User.objects.filter(admin_id=admin_id, is_active=True).exclude(role="KYC_TEAM")

            # include the admin user itself as option
            assign_qs = assign_qs | User.objects.filter(id=admin_id, is_active=True).exclude(role="KYC_TEAM")

        assign_qs = assign_qs.distinct().order_by("first_name", "last_name", "username")

        assign_users = [
            {
                "id": u.id,
                "name": (u.get_full_name() or u.username).strip(),
                "username": u.username,
                "role":u.role,
            }
            for u in assign_qs
        ]

        data = {
            "classifications": LeadClassificationTreeSerializer(
                classifications, many=True
            ).data,
            "sources": LeadSourceTreeSerializer(sources, many=True).data,
            "stages": LeadStageSerializer(stages, many=True).data,
            "purposes": LeadPurposeSerializer(purposes, many=True).data,
            "statuses": LeadStatusWithSubsSerializer(statuses, many=True).data,
            "offering_types": OfferingTypeSerializer(
                offering_types, many=True
            ).data,
            "unit_configurations": UnitConfigurationSerializer(
                unit_configurations, many=True
            ).data,
            # 👇 NEW: assign-to / owner candidate users
            "assign_users": assign_users,
        }
        return Response(data, status=200)


class LeadClassificationViewSet(viewsets.ModelViewSet):
    queryset = LeadClassification.objects.all()
    serializer_class = LeadClassificationTreeSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")




class LeadSourceViewSet(viewsets.ModelViewSet):
    queryset = LeadSource.objects.all()
    serializer_class = LeadSourceTreeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")



class LeadStageViewSet(viewsets.ModelViewSet):
    queryset = LeadStage.objects.all()
    serializer_class = LeadStageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")



class LeadStatusViewSet(viewsets.ModelViewSet):
    queryset = LeadStatus.objects.all()
    serializer_class = LeadStatusWithSubsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")


class LeadSubStatusViewSet(viewsets.ModelViewSet):
    queryset = LeadSubStatus.objects.select_related("status").all()
    serializer_class = LeadSubStatusSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(status__project_id__in=allowed_ids)

        status_id = self.request.query_params.get("status_id")
        if status_id:
            qs = qs.filter(status_id=status_id)

        return qs.order_by("name")



class LeadPurposeViewSet(viewsets.ModelViewSet):
    queryset = LeadPurpose.objects.all()
    serializer_class = LeadPurposeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")



class ProjectLeadViewSet(viewsets.ModelViewSet):
    queryset = ProjectLead.objects.select_related("project").all()
    serializer_class = ProjectLeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")



class LeadBudgetOfferViewSet(viewsets.ModelViewSet):
    queryset = LeadBudgetOffer.objects.select_related("project_lead").all()
    serializer_class = LeadBudgetOfferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")



class ProjectLeadSiteVisitSettingViewSet(viewsets.ModelViewSet):
    queryset = ProjectLeadSiteVisitSetting.objects.select_related("project_lead").all()
    serializer_class = ProjectLeadSiteVisitSettingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")

class ProjectLeadReportingViewSet(viewsets.ModelViewSet):
    queryset = ProjectLeadReporting.objects.select_related("project_lead").all()
    serializer_class = ProjectLeadReportingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        allowed_ids = _project_ids_for_user(self.request.user)
        qs = qs.filter(project_id__in=allowed_ids)

        pid = self.request.query_params.get("project_id")
        if not pid:
            return qs.none()  # Option A: project_id required

        assert_project_allowed(self.request, pid)
        return qs.filter(project_id=pid).order_by("order", "name")


class NewLeadAssignmentRuleViewSet(viewsets.ModelViewSet):
    queryset = NewLeadAssignmentRule.objects.select_related("project_lead", "project", "source").prefetch_related("assignees")
    serializer_class = NewLeadAssignmentRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        pid = self.request.query_params.get("project_id")
        if pid:
            qs = qs.filter(project_lead__project_id=pid)
        return qs.order_by("-created_at")


class ProjectLeadSetupUpsertAPIView(APIView):
    """
    POST /api/v2/leads/setup/
    Body: ProjectLeadSetupWriteSerializer payload
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ser = ProjectLeadSetupWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = ser.save()
        return Response(result, status=status.HTTP_200_OK)
