from rest_framework import viewsets, permissions
from .models import (
    VisitingHalf,
    FamilySize,
    ResidencyOwnerShip,
    PossienDesigned,
    Occupation,
    Designation,
)
from .serializers import (
    VisitingHalfSerializer,
    FamilySizeSerializer,
    ResidencyOwnerShipSerializer,
    PossienDesignedSerializer,
    OccupationSerializer,
    DesignationSerializer,
)
from leadmanage.models import ProjectLead   


class IsAuthenticatedAndActive(permissions.IsAuthenticated):
    pass


class ProjectLeadLookupViewSetMixin(viewsets.ModelViewSet):
    """
    Supports filters:
      ?project_id=<project>
      OR ?project_lead_id=<id>

    Har model per-project lead scoped hai.
    """
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        qs = self.queryset
        p = self.request.query_params

        pl_id = p.get("project_lead_id")
        proj_id = p.get("project_id")

        if pl_id:
            qs = qs.filter(project_lead_id=pl_id)
        elif proj_id:
            qs = qs.filter(project_lead__project_id=proj_id)

        return qs.order_by("name")


class VisitingHalfViewSet(ProjectLeadLookupViewSetMixin):
    queryset = VisitingHalf.objects.all()
    serializer_class = VisitingHalfSerializer


class FamilySizeViewSet(ProjectLeadLookupViewSetMixin):
    queryset = FamilySize.objects.all()
    serializer_class = FamilySizeSerializer


class ResidencyOwnerShipViewSet(ProjectLeadLookupViewSetMixin):
    queryset = ResidencyOwnerShip.objects.all()
    serializer_class = ResidencyOwnerShipSerializer


class PossienDesignedViewSet(ProjectLeadLookupViewSetMixin):
    queryset = PossienDesigned.objects.all()
    serializer_class = PossienDesignedSerializer


class OccupationViewSet(ProjectLeadLookupViewSetMixin):
    queryset = Occupation.objects.all()
    serializer_class = OccupationSerializer


class DesignationViewSet(ProjectLeadLookupViewSetMixin):
    queryset = Designation.objects.all()
    serializer_class = DesignationSerializer
