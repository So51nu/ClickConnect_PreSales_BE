from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from costsheet.models import CostSheetStatus

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from common.tenancy import assert_project_allowed, get_allowed_project_ids

from salelead.models import SalesLead
from clientsetup.models import (
    Project,
    Inventory,
    InventoryStatus,
    AvailabilityStatus,
    PaymentPlan,
    CommercialOffer,
    OfferTargetType,
)
from .pdf_utils import generate_quotation_pdf
from .models import ProjectCostSheetTemplate
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework import viewsets
from salelead.models import SalesLead, InterestedLeadUnit
from clientsetup.models import Project, Inventory, InventoryStatus, AvailabilityStatus
from .models import ProjectCostSheetTemplate
from clientsetup.models import Project
from .models import CostSheetTemplate, ProjectCostSheetTemplate
from django.db.models import Q, Count
from rest_framework.decorators import action
from .serializers import (
    CostSheetTemplateSerializer,
    ProjectCostSheetTemplateSerializer,
    CostSheetTemplateBulkCreateOrMapSerializer,
    CostSheetTemplateWithProjectMappingSerializer,
)
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q
from rest_framework.decorators import action


class IsAdminUser(permissions.BasePermission):
    """
    Basic admin permission.
    Adjust to your own role logic if needed.
    """

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        role = getattr(u, "role", "")
        role_upper = role.upper() if isinstance(role, str) else ""
        return bool(getattr(u, "is_staff", False) or role_upper in["ADMIN","FULL_CONTROL"])

class CostSheetTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for master CostSheetTemplate (ADMIN + FULL_CONTROL).
    """

    serializer_class = CostSheetTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        user = self.request.user

        # staff sees everything
        if user.is_staff:
            return CostSheetTemplate.objects.all()

        role = getattr(user, "role", "")
        role_code = role.upper() if isinstance(role, str) else getattr(role, "code", None)

        # ADMIN sees own templates
        if role_code == "ADMIN":
            return CostSheetTemplate.objects.filter(created_by=user)

        # FULL_CONTROL sees admin's templates
        if role_code == "FULL_CONTROL":
            admin_user = getattr(user, "admin", None)
            if admin_user:
                return CostSheetTemplate.objects.filter(created_by=admin_user)
            return CostSheetTemplate.objects.none()

        return CostSheetTemplate.objects.none()


    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create_or_map(self, request, *args, **kwargs):
        """
        POST /api/costsheet/cost-sheet-templates/bulk-create/

        Mode 1: New template + mapping to multiple projects
        Mode 2: Existing template (template_id) + mapping to multiple projects
        """
        serializer = CostSheetTemplateBulkCreateOrMapSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            serializer.to_representation(result),
            status=status.HTTP_201_CREATED,
        )


class ProjectCostSheetTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for project ↔ template mapping.
    """

    serializer_class = ProjectCostSheetTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    def get_queryset(self):
        allowed_ids = get_allowed_project_ids(self.request.user)
        qs = ProjectCostSheetTemplate.objects.filter(project_id__in=allowed_ids)

        project_id = self.request.query_params.get("project_id")
        if project_id:
            assert_project_allowed(self.request, project_id)
            qs = qs.filter(project_id=project_id)

        template_id = self.request.query_params.get("template_id")
        if template_id:
            qs = qs.filter(template_id=template_id)

        return qs



class CostSheetTemplateByProjectAPIView(APIView):
    """
    GET /api/costsheet/cost-sheet-templates/by-project/?project_id=...

    If request.user is admin:
      - Returns ALL templates created_by = request.user
      - For each template, nested "mapping" field shows mapping for that project (if exists).
    """

    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response(
                {"detail": "project_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assert_project_allowed(request, project_id)
        project = get_object_or_404(Project, pk=project_id)

        templates = CostSheetTemplate.objects.filter(
            created_by=request.user
        ).prefetch_related("project_mappings")

        serializer = CostSheetTemplateWithProjectMappingSerializer(
            templates,
            many=True,
            context={"request": request, "project_id": project.id},
        )

        return Response(
            {
                "project": {
                    "id": project.id,
                    "name": getattr(project, "name", str(project)),
                },
                "templates": serializer.data,
            },
            status=status.HTTP_200_OK,
        )



class CostSheetLeadInitAPIView(APIView):
    """
    GET /api/costsheet/lead/<lead_id>/init/

    - Takes lead_id
    - Gets project, project cost sheet template
    - Calculates valid_till from template.validity_days
    - Sends:
        - lead info
        - project info + price_per_sqft
        - quotation template snapshot (taxes, T&C, etc.)
        - payment plans + slabs for this project
        - customer offers valid for this project
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lead_id):
        allowed_ids = get_allowed_project_ids(request.user)

        lead = get_object_or_404(
            SalesLead.objects.select_related("project"),
            pk=lead_id,
            project_id__in=allowed_ids,
        )

        project = lead.project
        today = timezone.now().date()

        # ------------------ Template & validity ------------------
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

            # build absolute URL for logo if present
            logo_url = None
            if tpl.company_logo:
                try:
                    logo_url = request.build_absolute_uri(tpl.company_logo.url)
                except Exception:
                    # fallback – relative path
                    logo_url = tpl.company_logo.url

            template_data = {
                "project_template_id": pct.id,
                "template_id": tpl.id,

                # 🔹 Company + visual header
                "company_name": tpl.company_name,
                "company_logo_url": logo_url,
                "quotation_header": tpl.quotation_header,
                "quotation_subheader": tpl.quotation_subheader,

                # 🔹 Validity
                "validity_days": tpl.validity_days,

                # 🔹 Taxes / Charges
                "gst_percent": str(tpl.gst_percent),
                "share_application_money_membership_fees": (
                    str(tpl.share_application_money_membership_fees)
                    if tpl.share_application_money_membership_fees is not None
                    else None
                ),
                "development_charges_psf": (
                    str(tpl.development_charges_psf)
                    if tpl.development_charges_psf is not None
                    else None
                ),
                "electrical_watern_n_all_charges": (
                    str(tpl.electrical_watern_n_all_charges)
                    if tpl.electrical_watern_n_all_charges is not None
                    else None
                ),
                "provisional_maintenance_psf": (
                    str(tpl.provisional_maintenance_psf)
                    if tpl.provisional_maintenance_psf is not None
                    else None
                ),
                "provisional_maintenance_months": (
                    tpl.provisional_maintenance_months
                    if tpl.provisional_maintenance_months is not None
                    else None
                ),
                "stamp_duty_percent": str(tpl.stamp_duty_percent),
                "registration_amount": str(tpl.registration_amount),
                "legal_fee_amount": str(tpl.legal_fee_amount),

                # 🔹 Possessional charges (NEW)
                "is_possessional_charges": tpl.is_possessional_charges,
                "possessional_gst_percent": str(tpl.possessional_gst_percent),

                # 🔹 Payment plan requirement (NEW)
                "is_plan_required": tpl.is_plan_required,

                # 🔹 T&C + extra config JSON
                "terms_and_conditions": tpl.terms_and_conditions,
                "config": tpl.config,
            }


        # ------------------ Payment Plans + Slabs ------------------
        plans_qs = (
            PaymentPlan.objects
            .filter(project=project)
            .prefetch_related("slabs")
            .order_by("name")
        )

        payment_plans_data = []
        for plan in plans_qs:
            slabs_data = []
            for slab in plan.slabs.all():
                slabs_data.append({
                    "id": slab.id,
                    "order_index": slab.order_index,
                    "name": slab.name,
                    "percentage": str(slab.percentage),
                    "days": slab.days,
                })

            payment_plans_data.append({
                "id": plan.id,
                "code": plan.code,
                "name": plan.name,
                "total_percentage": plan.total_percentage,
                "slabs": slabs_data,
            })

        # ------------------ Customer Offers for this project ------------------
        admin_user = getattr(project, "belongs_to", None)

        offers_qs = CommercialOffer.objects.filter(
            target_type=OfferTargetType.CUSTOMER,
            is_active=True,
        )

        if admin_user:
            offers_qs = offers_qs.filter(admin=admin_user)

        # scope: project specific OR global (project is null)
        offers_qs = offers_qs.filter(
            Q(project__isnull=True) | Q(project=project)
        )

        # validity: (valid_from <= today or null) AND (valid_till >= today or null)
        offers_qs = offers_qs.filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=today),
            Q(valid_till__isnull=True) | Q(valid_till__gte=today),
        ).order_by("name")

        offers_data = []
        for offer in offers_qs:
            offers_data.append({
                "id": offer.id,
                "name": offer.name,
                "code": offer.code,
                "description": offer.description,
                "value_type": offer.value_type,
                "amount": str(offer.amount) if offer.amount is not None else None,
                "percentage": str(offer.percentage) if offer.percentage is not None else None,
                "gift_description": offer.gift_description,
                "min_booking_amount": (
                    str(offer.min_booking_amount)
                    if offer.min_booking_amount is not None else None
                ),
                "valid_from": offer.valid_from,
                "valid_till": offer.valid_till,
                "scope": {
                    "project_id": offer.project_id,
                    "project_name": offer.project.name if offer.project_id else None,
                },
            })

        # ------------------ Final payload ------------------
        data = {
            "lead": {
                "id": lead.id,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "full_name": (
                    f"{lead.first_name or ''} {lead.last_name or ''}"
                ).strip(),
                "email": lead.email,
                "mobile_number": lead.mobile_number,
            },
            "project": {
                "id": project.id,
                "name": project.name,
                "price_per_sqft": (
                    str(project.price_per_sqft)
                    if project.price_per_sqft is not None else None
                ),
                "price_per_parking": (
                    str(project.price_per_parking)
                    if getattr(project, "price_per_parking", None) is not None
                    else None
                ),
		"address":(
                    str(project.office_address)
                    if project.office_address is not None else None)
            },
            "today": today,
            "valid_till": valid_till,
            "template": template_data,
            "payment_plans": payment_plans_data,
            "offers": offers_data,
        }

        return Response(data, status=status.HTTP_200_OK)



class ProjectAvailableInventoryAPIView(APIView):
    """
    GET /api/costsheet/available-inventory/?project_id=<id>&lead_id=<id?>

    - Returns available inventory for a project
    - Nested as: tower -> floors -> inventories
    - If lead_id given, marks is_interested for that lead
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        lead_id = request.query_params.get("lead_id")

        if not project_id:
            return Response(
                {"detail": "project_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = get_object_or_404(Project, pk=project_id)

        inv_qs = (
            Inventory.objects
            .select_related("project", "tower", "floor", "unit", "configuration")
            .filter(
                project=project,
                availability_status=AvailabilityStatus.AVAILABLE,
            )
        )

        # ---------------------------------------
        # Interested units for this lead (optional)
        # ---------------------------------------
        interested_unit_ids = set()
        if lead_id:
            interested_unit_ids = set(
                InterestedLeadUnit.objects.filter(sales_lead_id=lead_id)
                .values_list("unit_id", flat=True)
            )

        # ---------------------------------------
        # Build nested structure: tower -> floor -> inventories
        # ---------------------------------------
        towers_map = {}  # tower_id -> { tower_id, tower_name, floors: { floor_id: {...} } }

        for inv in inv_qs:
            unit = inv.unit

            # card for one inventory
            inv_card = {
                "inventory_id": inv.id,
                "unit_id": unit.id if unit else None,
                "unit_no": unit.unit_no if unit else "",
                "unit_type": getattr(unit.unit_type, "name", "") if unit and unit.unit_type_id else "",
                "configuration": getattr(inv.configuration, "name", "") if inv.configuration_id else "",
                "status": inv.unit_status,
                "availability_status": inv.availability_status,
                "carpet_sqft": str(inv.carpet_sqft) if inv.carpet_sqft is not None else None,
                "rera_area_sqft": str(inv.rera_area_sqft) if inv.rera_area_sqft is not None else None,
                "saleable_sqft": str(inv.saleable_sqft) if inv.saleable_sqft is not None else None,
                "rate_psf": str(inv.rate_psf) if inv.rate_psf is not None else None,
                "agreement_value": str(inv.agreement_value) if inv.agreement_value is not None else None,
                "total_cost": str(inv.total_cost) if inv.total_cost is not None else None,
                "is_interested": bool(unit and unit.id in interested_unit_ids),
            }

            tower_id = inv.tower_id or 0
            floor_id = inv.floor_id or 0

            # --- tower group ---
            if tower_id not in towers_map:
                towers_map[tower_id] = {
                    "tower_id": tower_id,
                    "tower_name": inv.tower.name if inv.tower_id else "",
                    "floors": {},  # floor_id -> floor_group
                }
            tower_group = towers_map[tower_id]

            # --- floor group under that tower ---
            if floor_id not in tower_group["floors"]:
                tower_group["floors"][floor_id] = {
                    "floor_id": floor_id,
                    "floor_number": inv.floor.number if inv.floor_id else "",
                    "inventories": [],
                }
            floor_group = tower_group["floors"][floor_id]

            floor_group["inventories"].append(inv_card)

        # ---------------------------------------
        # Convert maps → sorted lists
        # ---------------------------------------
        nested_results = []

        for t in towers_map.values():
            floors_list = list(t["floors"].values())
            # sort floors by floor_number (string; change if you want numeric)
            floors_list.sort(key=lambda f: f["floor_number"])
            t["floors"] = floors_list
            nested_results.append(t)

        # sort towers by name
        nested_results.sort(key=lambda t: t["tower_name"])

        # ---------------------------------------
        # Final response
        # ---------------------------------------
        return Response(
            {
                "project": {
                    "id": project.id,
                    "name": project.name,
                },
                "lead_id": int(lead_id) if lead_id else None,
                "tower_count": len(nested_results),
                "results": nested_results,
            },
            status=status.HTTP_200_OK,
        )


from rest_framework import generics, permissions
from .serializers import CostSheetSerializer,CostSheetShortSerializer
from .models import CostSheet

import logging
log = logging.getLogger(__name__)

class CostSheetCreateAPIView(generics.CreateAPIView):
    """
    POST /api/costsheet/cost-sheets/all/

    Creates a CostSheet + nested additional_charges + applied_offers.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CostSheetSerializer
    queryset = CostSheet.objects.all()



class CostSheetViewSet(viewsets.ModelViewSet):
    """
    /api/costsheet/cost-sheets/  (router)
      GET    -> list
      POST   -> create
    /api/costsheet/cost-sheets/<id>/
      GET    -> retrieve
      PUT    -> full update
      PATCH  -> partial update
      DELETE -> delete

    Extra:
    /api/costsheet/cost-sheets/my-quotations/
      GET    -> quotations prepared_by = request.user

    /api/costsheet/cost-sheets/<id>/deep/
      GET    -> single quotation full detail (deep)
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CostSheetSerializer

    def get_queryset(self):
        qs = (
            CostSheet.objects
            .select_related("project", "lead", "inventory", "prepared_by")
            .order_by("-created_at")
        )

        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)

        lead_id = self.request.query_params.get("lead_id")
        if lead_id:
            qs = qs.filter(lead_id=lead_id)

        return qs

    @action(detail=False, methods=["get"], url_path="my-quotations")
    def my_quotations(self, request):
        """
        GET /api/costsheet/cost-sheets/my-quotations/?search=&page=&deep=true|false
        """
        user = request.user

        qs = (
            CostSheet.objects
            .filter(prepared_by=user)
            .annotate(attachments_count=Count("attachments"))
            .order_by("-created_at")
        )

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(quotation_no__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(project_name__icontains=search)
            )

        deep = request.query_params.get("deep") in ["1", "true", "True", "yes"]

        # ---- DEEP LIST (full serializer) ----
        if deep:
            page = self.paginate_queryset(qs)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data)

        # ---- SHALLOW LIST ----
        def serialize_item(cs: CostSheet):
            return {
                "id": cs.id,
                "quotation_no": cs.quotation_no,
                "customer_name": cs.customer_name,
                "project_name": cs.project_name,
                "prepared_by_name": (
                    cs.prepared_by.get_full_name()
                    if cs.prepared_by and cs.prepared_by.get_full_name()
                    else None
                ),
                "prepared_by_username": (
                    cs.prepared_by.username if cs.prepared_by else None
                ),
                "date": cs.date,
                "valid_till": cs.valid_till,
                "net_payable_amount": cs.net_payable_amount,
                "attachments_count": getattr(cs, "attachments_count", 0),
            }

        page = self.paginate_queryset(qs)
        if page is not None:
            data = [serialize_item(obj) for obj in page]
            return self.get_paginated_response(data)

        data = [serialize_item(obj) for obj in qs]
        return Response(data)


    @action(detail=True, methods=["get"], url_path="deep")
    def deep_detail(self, request, pk=None):
        instance = self.get_object()

        # sirf jisne banaya woh hi dekh sakta (tumhari existing logic)
        if instance.prepared_by_id and instance.prepared_by_id != request.user.id:
            return Response(
                {"detail": "Not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # non-draft ke liye PDF ensure (as is)
        if instance.status != CostSheetStatus.DRAFT:
            try:
                has_pdf = instance.attachments.filter(label="Quotation PDF").exists()
            except AttributeError:
                has_pdf = False

            if not has_pdf:
                try:
                    generate_quotation_pdf(instance, request=request)
                except Exception:
                    log.exception(
                        "Error auto-generating quotation PDF in deep_detail"
                    )

        serializer = self.get_serializer(instance)
        data = serializer.data

        # ====== Yaha se COST SHEET TEMPLATE INFO ADD KARO ======
        # CostSheet -> ProjectCostSheetTemplate (FK: project_template)
        proj_tpl = getattr(instance, "project_template", None)
        tpl = proj_tpl.template if proj_tpl is not None else None

        if tpl is not None:
            data["template"] = {
                "id": tpl.id,
                "company_name": tpl.company_name,
                "quotation_header": tpl.quotation_header,
                "quotation_subheader": tpl.quotation_subheader,
                "validity_days": tpl.validity_days,

                # ye 4 tumne specifically maange the:
                "share_application_money_membership_fees": (
                    str(tpl.share_application_money_membership_fees)
                    if tpl.share_application_money_membership_fees is not None
                    else None
                ),
                "development_charges_psf": (
                    str(tpl.development_charges_psf)
                    if tpl.development_charges_psf is not None
                    else None
                ),
                "electrical_watern_n_all_charges": (
                    str(tpl.electrical_watern_n_all_charges)
                    if tpl.electrical_watern_n_all_charges is not None
                    else None
                ),
                "provisional_maintenance_psf": (
                    str(tpl.provisional_maintenance_psf)
                    if tpl.provisional_maintenance_psf is not None
                    else None
                ),

                # optional: agar frontend ko hint chahiye to ye bhi de sakte ho
                "gst_percent": str(tpl.gst_percent),
                "stamp_duty_percent": str(tpl.stamp_duty_percent),
                "registration_amount": str(tpl.registration_amount),
                "legal_fee_amount": str(tpl.legal_fee_amount),
            }

        return Response(data)


    @action(detail=True, methods=["post"], url_path="generate-pdf")
    def generate_pdf(self, request, pk=None):
        costsheet = self.get_object()

        if costsheet.prepared_by_id and costsheet.prepared_by_id != request.user.id:
            return Response(
                {"detail": "Not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )

        is_draft = costsheet.status == CostSheetStatus.DRAFT
        force = request.data.get("force") in ["1", "true", "True", "yes"]

        try:
            att = generate_quotation_pdf(
                costsheet,
                request=request,
                force=(is_draft or force),
            )
        except RuntimeError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            log.exception("Error generating quotation PDF")
            return Response(
                {"detail": "Failed to generate PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        data = {
            "id": costsheet.id,
            "quotation_no": costsheet.quotation_no,
            "status": costsheet.status,
            "status_label": costsheet.status_label,
            "pdf_url": request.build_absolute_uri(att.file.url),
        }
        return Response(data, status=status.HTTP_200_OK)

