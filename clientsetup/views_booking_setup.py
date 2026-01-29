# clientsetup/views_booking_setup.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.shortcuts import get_object_or_404

from .models import Project, Tower, PaymentPlan
from .serializers_booking_setup import (
    ProjectMiniSerializer,
    TowerWithFloorsSerializer,
    PaymentPlanSerializer,
)



class ProjectBookingSetupAPIView(APIView):
    """
    GET /api/client/booking-setup/?project_id=2
    Optional:
        ?lead_id=<lead_id>   → will also attach cost sheet init data
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        lead_id = request.query_params.get("lead_id")

        if not project_id:
            return Response(
                {"detail": "project_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --------------------------------------------------------------------
        # BASE PROJECT BOOKING DATA
        # --------------------------------------------------------------------
        project = get_object_or_404(Project, pk=project_id)

        towers_qs = (
            project.towers.all()
            .prefetch_related(
                "floors__units__inventory_items__unit_type",
                "floors__units__inventory_items__configuration",
                "floors__units__inventory_items__facing",
                "floors__units",
                "floors",
            )
        )

        payment_plans_qs = (
            project.payment_plans.all()
            .prefetch_related("slabs")
        )

        base_payload = {
            "project": ProjectMiniSerializer(project).data,
            "towers": TowerWithFloorsSerializer(towers_qs, many=True).data,
            "payment_plans": PaymentPlanSerializer(payment_plans_qs, many=True).data,
        }

        # --------------------------------------------------------------------
        # OPTIONAL: MERGE LEAD COST-SHEET INITIAL DATA
        # --------------------------------------------------------------------
        if lead_id:
            lead = get_object_or_404(
                SalesLead.objects.select_related("project"),
                pk=lead_id,
            )
            today = timezone.now().date()

            # ------------------ Template ------------------
            pct = (
                ProjectCostSheetTemplate.objects
                .select_related("template")
                .filter(project=project, is_active=True)
                .order_by("-created_at")
                .first()
            )

            valid_till = today
            template_data = None

            if pct and pct.template:
                tpl = pct.template
                days = tpl.validity_days or 0
                valid_till = today + timedelta(days=days)

                template_data = {
                    "project_template_id": pct.id,
                    "template_id": tpl.id,
                    "quotation_header": tpl.quotation_header,
                    "quotation_subheader": tpl.quotation_subheader,
                    "validity_days": tpl.validity_days,
                    "terms_and_conditions": tpl.terms_and_conditions,
                    "gst_percent": str(tpl.gst_percent),
                    "stamp_duty_percent": str(tpl.stamp_duty_percent),
                    "registration_amount": str(tpl.registration_amount),
                    "legal_fee_amount": str(tpl.legal_fee_amount),
                }

            # ------------------ Payment Plans ------------------
            plans_qs = (
                PaymentPlan.objects
                .filter(project=project)
                .prefetch_related("slabs")
            )

            payment_plans_data = []
            for plan in plans_qs:
                slabs_data = [
                    {
                        "id": slab.id,
                        "order_index": slab.order_index,
                        "name": slab.name,
                        "percentage": str(slab.percentage),
                        "days": slab.days,
                    }
                    for slab in plan.slabs.all()
                ]

                payment_plans_data.append({
                    "id": plan.id,
                    "code": plan.code,
                    "name": plan.name,
                    "total_percentage": plan.total_percentage,
                    "slabs": slabs_data,
                })

            # ------------------ Offers ------------------
            admin_user = getattr(project, "belongs_to", None)

            offers_qs = CommercialOffer.objects.filter(
                target_type=OfferTargetType.CUSTOMER,
                is_active=True,
            )

            if admin_user:
                offers_qs = offers_qs.filter(admin=admin_user)

            offers_qs = offers_qs.filter(
                Q(project__isnull=True) | Q(project=project)
            ).filter(
                Q(valid_from__isnull=True) | Q(valid_from__lte=today),
                Q(valid_till__isnull=True) | Q(valid_till__gte=today)
            ).order_by("name")

            offers_data = []
            for offer in offers_qs:
                offers_data.append({
                    "id": offer.id,
                    "name": offer.name,
                    "code": offer.code,
                    "description": offer.description,
                    "value_type": offer.value_type,
                    "amount": str(offer.amount) if offer.amount else None,
                    "percentage": str(offer.percentage) if offer.percentage else None,
                    "gift_description": offer.gift_description,
                    "min_booking_amount": (
                        str(offer.min_booking_amount)
                        if offer.min_booking_amount else None
                    ),
                    "valid_from": offer.valid_from,
                    "valid_till": offer.valid_till,
                    "scope": {
                        "project_id": offer.project_id,
                        "project_name": offer.project.name if offer.project_id else None,
                    },
                })

            # ------------------ Lead Packet ------------------
            lead_payload = {
                "lead_costsheet": {
                    "lead": {
                        "id": lead.id,
                        "first_name": lead.first_name,
                        "last_name": lead.last_name,
                        "full_name": f"{lead.first_name} {lead.last_name}".strip(),
                        "email": lead.email,
                        "mobile_number": lead.mobile_number,
                    },
                    "project": {
                        "id": project.id,
                        "name": project.name,
                        "price_per_sqft": (
                            str(project.price_per_sqft)
                            if project.price_per_sqft else None
                        ),
                    },
                    "today": today,
                    "valid_till": valid_till,
                    "template": template_data,
                    "payment_plans": payment_plans_data,
                    "offers": offers_data,
                }
            }

            # MERGE IT INTO ORIGINAL RESPONSE
            base_payload.update(lead_payload)

        return Response(base_payload, status=status.HTTP_200_OK)

