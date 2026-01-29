# salelead/views_interested_units.py

from django.db import models as dj_models
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, permissions
from .models import InterestedLeadUnit
from .serializers import InterestedLeadUnitSerializer
from .views import _project_ids_for_user        

class IsAuthenticatedAndActive(permissions.IsAuthenticated):
    pass

class InterestedLeadUnitViewSet(viewsets.ModelViewSet):
    """
    /api/sales/interested-units/
      GET  ?sales_lead=<id>   -> list mappings for that lead
      POST { sales_lead, unit } -> add interested unit
      DELETE /<id>/          -> remove one mapping
    """
    serializer_class = InterestedLeadUnitSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        user = self.request.user
        project_ids = _project_ids_for_user(user)

        qs = (
            InterestedLeadUnit.objects
            .select_related(
                "sales_lead",
                "unit",
                "unit__project",
                "unit__tower",
                "unit__floor",
            )
            .filter(unit__project_id__in=project_ids)
        )

        role = getattr(user, "role", None)

        # Same role logic as SalesLeadViewSet
        if role == "ADMIN" or user.is_staff:
            pass
        elif role == "SALES":
            qs = qs.filter(
                dj_models.Q(sales_lead__created_by=user)
                | dj_models.Q(sales_lead__current_owner=user)
                | dj_models.Q(sales_lead__assign_to=user)
            )
        else:
            qs = qs.filter(
                dj_models.Q(sales_lead__current_owner=user)
                | dj_models.Q(sales_lead__assign_to=user)
            )

        # Extra query params
        p = self.request.query_params

        sales_lead_id = p.get("sales_lead")
        if sales_lead_id:
            qs = qs.filter(sales_lead_id=sales_lead_id)

        unit_id = p.get("unit")
        if unit_id:
            qs = qs.filter(unit_id=unit_id)

        return qs.order_by("-id")
