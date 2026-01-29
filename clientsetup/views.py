from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from .serializers import (
    ProjectSerializer, TowerSerializer, FloorSerializer, FloorDocumentSerializer,
    UnitSerializer, MilestonePlanSerializer, MilestoneSlabSerializer
)
from salelead.models import SalesLead,SalesLeadUpdateStatus
from django.db.models import Q
from .permissions import IsStaffOrAdminForUnsafe
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from accounts.models import ClientBrand
from accounts.models import Role
from setup.models import (
    ProjectType, TowerType, UnitType, Facing, ParkingType,
    BankType, BankCategory, LoanProduct,    VisitingHalf,       
    FamilySize,         
    ResidencyOwnerShip, 
    PossienDesigned,    
    Occupation,         
    Designation,UnitConfiguration
)
from accounts.serializers import ClientBrandSerializer
from salelead.models import SalesLeadStatusHistory
from leadmanage.models import LeadStatus,  LeadSubStatus
from .models import (
    Project, Tower, Floor, FloorDocument, Unit, MilestonePlan, MilestoneSlab,
    PaymentPlan, PaymentSlab,ApprovalStatus,
    Bank, BankBranch, ProjectBank, ProjectBankProduct,
    Notification, NotificationDispatchLog, ReadStatus,Inventory,
    Project, Tower, Floor, Unit,
    ProjectStatus, FloorStatus, UnitStatus, MilestonePlanStatus, CalcMode,
    Bank, BankBranch, ProjectBank, ProjectBankProduct

)
from .serializers import (
    PaymentPlanSerializer, PaymentSlabSerializer,
    BankSerializer, BankBranchSerializer,
    ProjectBankSerializer, ProjectBankProductSerializer,
    NotificationSerializer, NotificationDispatchLogSerializer
)
from django.db.models import Count
from leadmanage.models import (
    VisitingHalf,
    FamilySize,
    ResidencyOwnerShip,
    PossienDesigned,
    Occupation,
    Designation,
    LeadStatus,
)
from costsheet.serializers import CostSheetSerializer
class BaseOwnedQuerysetMixin:
    """
    FINAL FIX:
    ADMIN and FULL_CONTROL see the same data.
    """

    def _get_role(self, user):
        role = getattr(user, "role", None)
        if not role:
            return None
        if isinstance(role, str):
            return role.upper()
        return getattr(role, "code", None)

    def _get_owner_id(self, user):
        """
        Returns the ADMIN user id whose data should be visible
        """
        if user.is_staff:
            return None

        role = self._get_role(user)

        # ADMIN owns data
        if role == "ADMIN":
            return user.id

        # FULL_CONTROL sees admin's data
        if role == "FULL_CONTROL":
            return getattr(user, "admin_id", None)

        # SALES / RECEPTION
        return getattr(user, "admin_id", None)

    def filter_owned(self, qs, field="belongs_to_id"):
        user = self.request.user

        # staff sees everything
        if user.is_staff:
            return qs

        owner_id = self._get_owner_id(user)

        if owner_id:
            return qs.filter(**{field: owner_id})

        return qs.none()




from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction


class ProjectViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = Project.objects.all().select_related("project_type", "belongs_to")
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = (
            Project.objects
            .select_related("project_type", "belongs_to")
            .annotate(
                total_inventory=Count("inventories", distinct=True)  # 👈 uses Inventory.related_name
            )
            .order_by('-id')
        )
        return self.filter_owned(qs, field="belongs_to_id")
    
    @action(detail=False, methods=["GET"], url_path="tree")
    def project_tree(self, request):
        """
        GET /api/client/projects/tree/?project_id=<id>&include_units=true|false
        Permissions:
          - staff: any project
          - admin: only own projects
          - sales/reception: projects belonging to their admin
        """
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "project_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project_id = int(project_id)
        except ValueError:
            return Response({"detail": "project_id must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

        include_units = str(request.query_params.get("include_units", "false")).lower() in ("1", "true", "yes", "y")

        # fetch project
        try:
            project = Project.objects.only("id", "name", "status", "approval_status", "belongs_to_id").get(id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        # permission check
        u = request.user

        if u.is_staff:
            allowed = True

        elif getattr(u, "role", None) == Role.ADMIN:
            # Admin owns the project
            allowed = (project.belongs_to_id == u.id)

        elif getattr(u, "role", None) == Role.FULL_CONTROL:
            # Full control sees admin's projects
            allowed = (getattr(u, "admin_id", None) == project.belongs_to_id)

        elif getattr(u, "role", None) in (Role.SALES, Role.RECEPTION):
            allowed = (getattr(u, "admin_id", None) == project.belongs_to_id)

        else:
            allowed = False


        if not allowed:
            return Response({"detail": "Not allowed for this project."}, status=status.HTTP_403_FORBIDDEN)

        # ---------- NEW PART: total inventory count ----------
        total_inventory = Inventory.objects.filter(project_id=project.id).count()
        # -----------------------------------------------------

        # prefetch nested
        floor_qs = Floor.objects.only("id", "number", "tower_id").order_by("number")
        if include_units:
            unit_qs = Unit.objects.only("id", "unit_no", "status", "floor_id").order_by("unit_no")
            floor_qs = floor_qs.prefetch_related(Prefetch("units", queryset=unit_qs))

        tower_qs = (
            Tower.objects.filter(project_id=project.id)
            .only("id", "name", "project_id")
            .prefetch_related(Prefetch("floors", queryset=floor_qs))
            .order_by("name")
        )

        # build payload
        payload = {
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "approval_status": project.approval_status,
                "total_inventory": total_inventory,  # 👈 send count here
            },
            "towers": [],
        }

        for t in tower_qs:
            t_item = {"id": t.id, "name": t.name, "floors": []}
            for f in t.floors.all():
                f_item = {"id": f.id, "number": f.number}
                if include_units:
                    f_item["units"] = [
                        {"id": uu.id, "unit_no": uu.unit_no, "status": uu.status}
                        for uu in f.units.all()
                    ]
                t_item["floors"].append(f_item)
            payload["towers"].append(t_item)

        return Response(payload, status=status.HTTP_200_OK)


class TowerViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = Tower.objects.select_related("project", "tower_type", "project__belongs_to")
    serializer_class = TowerSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            Tower.objects.select_related("project", "tower_type", "project__belongs_to"),
            field="project__belongs_to_id",
        )
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class FloorViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = Floor.objects.select_related("tower", "tower__project", "tower__project__belongs_to")
    serializer_class = FloorSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            Floor.objects.select_related("tower", "tower__project", "tower__project__belongs_to"),
            field="tower__project__belongs_to_id",
        )
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(tower__project_id=project_id)
        return qs
    


class FloorDocumentViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = FloorDocument.objects.select_related(
        "floor", "floor__tower", "floor__tower__project", "floor__tower__project__belongs_to"
    )
    serializer_class = FloorDocumentSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            FloorDocument.objects.select_related(
                "floor", "floor__tower", "floor__tower__project", "floor__tower__project__belongs_to"
            ),
            field="floor__tower__project__belongs_to_id",
        )
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(floor__tower__project_id=project_id)
        return qs


class UnitViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = Unit.objects.select_related(
        "project", "tower", "floor",
        "project__belongs_to", "unit_type", "facing", "parking_type"
    )
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            Unit.objects.select_related(
                "project", "tower", "floor",
                "project__belongs_to", "unit_type", "facing", "parking_type"
            ),
            field="project__belongs_to_id",
        )
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class MilestoneSlabViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = MilestoneSlab.objects.select_related(
        "plan", "plan__project", "plan__project__belongs_to"
    )
    serializer_class = MilestoneSlabSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            MilestoneSlab.objects.select_related(
                "plan", "plan__project", "plan__project__belongs_to"
            ),
            field="plan__project__belongs_to_id",
        )

        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(plan__project_id=project_id)

        plan_id = self.request.query_params.get("plan_id")
        if plan_id:
            qs = qs.filter(plan_id=plan_id)

        return qs



class MilestonePlanViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    """
    Milestone Plans:
      - Normal CRUD (list, retrieve, create, update, delete)
      - Extra: POST /milestone-plans/bulk-create/ for bulk creation with nested slabs
    """

    queryset = MilestonePlan.objects.select_related(
        "project",
        "tower",
        "responsible_user",
        "verified_by",
        "project__belongs_to",
    )
    serializer_class = MilestonePlanSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        """
        User-owned plans filter + optional ?project_id=
        """
        qs = self.filter_owned(
            MilestonePlan.objects.select_related(
                "project",
                "tower",
                "responsible_user",
                "verified_by",
                "project__belongs_to",
            ),
            field="project__belongs_to_id",
        )

        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)

        return qs

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """
        POST /api/.../milestone-plans/bulk-create/

        Body example (LIST of plans):

        [
          {
            "project": 1,
            "tower": null,
            "name": "Plan A",
            "calc_mode": "PERCENTAGE",
            "amount": null,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "responsible_user": 7,
            "enable_pg_integration": false,
            "verified_by": null,
            "verified_date": null,
            "status": "DRAFT",
            "notes": "Some notes",
            "slabs": [
              {"name": "On Booking", "percentage": 10, "remarks": "10% on booking"},
              {"name": "On Plinth", "percentage": 15}
            ]
          },
          {
            "project": 1,
            "tower": 2,
            "name": "Tower 2 Plan",
            "calc_mode": "AMOUNT",
            "amount": 10000000,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "responsible_user": 7,
            "enable_pg_integration": false,
            "verified_by": null,
            "verified_date": null,
            "status": "DRAFT",
            "notes": "",
            "slabs": [
              {"name": "On Booking", "amount": 2500000},
              {"name": "On Slab 1", "amount": 2500000}
            ]
          }
        ]
        """
        if not isinstance(request.data, list):
            return Response(
                {"detail": "Expected a list of milestone plans."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(
            data=request.data,
            many=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            plans = serializer.save()

        # Re-serialize created objects (with IDs + nested slabs)
        out = self.get_serializer(plans, many=True)
        return Response(out.data, status=status.HTTP_201_CREATED)




class PaymentPlanViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = PaymentPlan.objects.select_related("project", "project__belongs_to")
    serializer_class = PaymentPlanSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            PaymentPlan.objects.select_related("project", "project__belongs_to"),
            field="project__belongs_to_id",
        )
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class PaymentSlabViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = PaymentSlab.objects.select_related("plan", "plan__project", "plan__project__belongs_to")
    serializer_class = PaymentSlabSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            PaymentSlab.objects.select_related("plan", "plan__project", "plan__project__belongs_to"),
            field="plan__project__belongs_to_id",
        )

        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(plan__project_id=project_id)

        plan_id = self.request.query_params.get("plan_id")
        if plan_id:
            qs = qs.filter(plan_id=plan_id)

        return qs



class BankViewSet(ModelViewSet):
    queryset = Bank.objects.select_related("bank_type", "bank_category")
    serializer_class = BankSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

class BankBranchViewSet(ModelViewSet):
    queryset = BankBranch.objects.select_related("bank", "bank__bank_type", "bank__bank_category")
    serializer_class = BankBranchSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

class ProjectBankViewSet(BaseOwnedQuerysetMixin, ModelViewSet):
    queryset = ProjectBank.objects.select_related("project", "project__belongs_to", "bank_branch", "bank_branch__bank")
    serializer_class = ProjectBankSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        qs = self.filter_owned(
            ProjectBank.objects.select_related("project", "project__belongs_to", "bank_branch", "bank_branch__bank"),
            field="project__belongs_to_id",
        )
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs



class NotificationViewSet(ModelViewSet):
    queryset = Notification.objects.select_related("project", "user")
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]

    def get_queryset(self):
        u = self.request.user
        qs = Notification.objects.all()
        if u.is_staff:
            return qs
        if getattr(u, "role", None) == "ADMIN":
            return qs.filter(Q(project__belongs_to_id=u.id) | Q(user=u))
        return qs.filter(user=u)

    @action(detail=True, methods=["POST"])
    def mark_read(self, request, pk=None):
        obj = self.get_object()
        if not (request.user.is_staff or request.user.id == obj.user_id):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        obj.read_status = ReadStatus.READ
        obj.save(update_fields=["read_status", "updated_at"])
        return Response({"status": "read"})


class NotificationDispatchLogViewSet(ModelViewSet):
    queryset = NotificationDispatchLog.objects.select_related("notification")
    serializer_class = NotificationDispatchLogSerializer
    permission_classes = [IsAuthenticated, IsStaffOrAdminForUnsafe]



class SetupBundleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        User = get_user_model()

        def choices_to_list(choices):
            return [{"code": c[0], "label": c[1]} for c in choices]

        # ---------- resolve scope admin ----------
        qp_admin_id = request.query_params.get("admin_id")
        target_admin_id = None

        if request.user.is_staff:
            target_admin_id = int(qp_admin_id) if qp_admin_id else None
        elif getattr(request.user, "role", None) in ( Role.ADMIN,Role.FULL_CONTROL):
            target_admin_id = request.user.id
        else:
            target_admin_id = getattr(request.user, "admin_id", None)

        users_payload = {"admin_id": target_admin_id, "items": []}

        if target_admin_id:
            admin_qs = User.objects.filter(id=target_admin_id)
            team_qs = User.objects.filter(admin_id=target_admin_id).exclude(id=target_admin_id)

            def map_user(u):
                return {
                    "id": u.id,
                    "username": u.username,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "role": getattr(u, "role", None),
                    "is_active": u.is_active,
                    "is_staff": u.is_staff,
                }

            users_payload["items"] = [*map(map_user, admin_qs), *map(map_user, team_qs)]

        # ---------- project_id from query params (for per-project lookups) ----------
        qp_project_id = request.query_params.get("project_id")
        project_id = None
        if qp_project_id:
            try:
                project_id = int(qp_project_id)
            except ValueError:
                project_id = None

        # pre-build lead update statuses (per project if given)
        update_statuses_qs = SalesLeadUpdateStatus.objects.filter(is_active=True)
        if project_id is not None:
            update_statuses_qs = update_statuses_qs.filter(project_id=project_id)

        data = {
            "user": {
                "id": request.user.id,
                "username": request.user.username,
                "role": getattr(request.user, "role", None),
                "is_staff": request.user.is_staff,
            },
            "users": users_payload,
            "statuses": {
                "project": choices_to_list(ProjectStatus.choices),
                "approval": choices_to_list(ApprovalStatus.choices),
                "floor": choices_to_list(FloorStatus.choices),
                "unit": choices_to_list(UnitStatus.choices),
                "milestone_plan": choices_to_list(MilestonePlanStatus.choices),
                "calc_mode": choices_to_list(CalcMode.choices),
            },
            "lookups": {
                "project_types": list(
                    ProjectType.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "tower_types": list(
                    TowerType.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "unit_types": list(
                    UnitType.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "unit_configurations": list(
                    UnitConfiguration.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "facings": list(
                    Facing.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "parking_types": list(
                    ParkingType.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "bank_types": list(
                    BankType.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "bank_categories": list(
                    BankCategory.objects.filter(is_active=True).values("id", "name", "code")
                ),
                "loan_products": list(
                    LoanProduct.objects.filter(is_active=True).values("id", "name", "code")
                ),

                # LEAD-RELATED LOOKUPS
                "visiting_half": list(
                    VisitingHalf.objects.filter(is_active=True)
                    .values("id", "name", "code", "project_lead_id")
                ),
                "family_sizes": list(
                    FamilySize.objects.filter(is_active=True)
                    .values("id", "name", "code", "project_lead_id")
                ),
                "residency_ownerships": list(
                    ResidencyOwnerShip.objects.filter(is_active=True)
                    .values("id", "name", "code", "project_lead_id")
                ),
                "possession_designed": list(
                    PossienDesigned.objects.filter(is_active=True)
                    .values("id", "name", "code", "project_lead_id")
                ),
                "occupations": list(
                    Occupation.objects.filter(is_active=True)
                    .values("id", "name", "code", "project_lead_id")
                ),
                "designations": list(
                    Designation.objects.filter(is_active=True)
                    .values("id", "name", "code", "project_lead_id")
                ),

                # Lead statuses + sub-statuses
                "lead_statuses": list(
                    LeadStatus.objects.select_related("project")
                    .values("id", "name", "project_id")
                ),
                "lead_sub_statuses": list(
                    LeadSubStatus.objects.select_related("status", "status__project")
                    .values("id", "name", "status_id", "status__project_id")
                ),

                # 🔹 NEW: per-project SalesLeadUpdateStatus
                "lead_update_statuses": list(
                    update_statuses_qs.values("id", "code", "label", "project_id")
                ),
            },
        }

        # ---------- OPTIONAL: lead-specific booking + quotation ----------
        lead_id = request.query_params.get("lead_id")
        lead_documents = {}

        if lead_id:
            try:
                lead = SalesLead.objects.get(pk=lead_id)
            except SalesLead.DoesNotExist:
                lead = None

            if lead:
                # latest booking
                latest_booking = (
                    lead.bookings
                    .select_related("unit", "project")
                    .prefetch_related("attachments")
                    .order_by("-created_at", "-id")
                    .first()
                )
                if latest_booking:
                    # try to find specific doc_type, else fallback to any attachment
                    b_att = (
                        latest_booking.attachments
                        .filter(doc_type__in=["BOOKING_FORM_PDF", "BOOKING_FORM", "AGREEMENT_PDF", "AGREEMENT"])
                        .order_by("-created_at")
                        .first()
                    ) or latest_booking.attachments.order_by("-created_at").first()

                    booking_pdf_url = None
                    if b_att and b_att.file:
                        booking_pdf_url = request.build_absolute_uri(b_att.file.url)

                    lead_documents["booking"] = {
                        "id": latest_booking.id,
                        "form_ref_no": latest_booking.form_ref_no,
                        "status": latest_booking.status,
                        "status_label": latest_booking.get_status_display(),
                        "booking_date": latest_booking.booking_date,
                        "booking_form_pdf": booking_pdf_url,
                    }

                # latest quotation / cost sheet
                latest_cs = (
                    lead.cost_sheets
                    .select_related("project", "prepared_by")
                    .prefetch_related("attachments")
                    .order_by("-created_at", "-id")
                    .first()
                )
                if latest_cs:
                    from costsheet.serializers import CostSheetSerializer

                    cs_ser = CostSheetSerializer(
                        latest_cs,
                        context={"request": request},
                    )
                    cs_data = cs_ser.data

                    lead_documents["quotation"] = {
                        "id": cs_data["id"],
                        "quotation_no": cs_data["quotation_no"],
                        "status": cs_data["status"],
                        "status_label": cs_data.get("status_label"),
                        "date": cs_data["date"],
                        "quotation_pdf": cs_data.get("quotation_pdf"),
                    }

        if lead_documents:
            data["lead_documents"] = lead_documents

        return Response(data, status=200)



from setup.models import OfferingType
from setup.serializers import OfferingTypeSerializer

from setup.models import OfferingType
from setup.serializers import OfferingTypeSerializer
from accounts.serializers import ClientBrandSerializer

class MyScopeView(APIView):
   
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ---- Query params ----
        include_units = str(request.query_params.get("include_units", "false")).lower() in ("1", "true", "yes", "y")
        only_project = str(request.query_params.get("only_project", "false")).lower() in ("1", "true", "yes", "y")
        unit_type = str(request.query_params.get("unit_type", "false")).lower() in ("1", "true", "yes", "y")
        u = request.user

        # ---- Decide admin_id correctly ----
        if u.is_staff:
            admin_id_raw = request.query_params.get("admin_id")
            if not admin_id_raw:
                return Response({"detail": "admin_id is required for staff."}, status=400)
            try:
                admin_id = int(admin_id_raw)
            except ValueError:
                return Response({"detail": "admin_id must be an integer."}, status=400)

        else:
            role = getattr(u, "role", None)
            role_code = role.upper() if isinstance(role, str) else getattr(role, "code", None)

            if role_code == "ADMIN":
                admin_id = u.id

            elif role_code == "FULL_CONTROL":
                admin_id = getattr(u, "admin_id", None)

            else:  # SALES / RECEPTION / others
                admin_id = getattr(u, "admin_id", None)

            if not admin_id:
                return Response(
                    {"detail": "This user is not linked to an admin."},
                    status=400,
                )



        # ---- Base project queryset (NOTE: price_per_sqft added in .only) ----
        project_qs = Project.objects.filter(belongs_to_id=admin_id).order_by("name")
                
        if only_project:
            projects = project_qs.only("id", "name", "status", "approval_status", "price_per_sqft","rera_no")
            payload = {
                "admin_id": admin_id,
                "projects": [],
                "brand": None,
            }

            # ---- ADD BRAND HERE ----
            try:
                brand = ClientBrand.objects.get(admin_id=admin_id)
                payload["brand"] = ClientBrandSerializer(brand, context={"request": request}).data
            except ClientBrand.DoesNotExist:
                payload["brand"] = None

            for p in projects:
                payload["projects"].append({
                    "id": p.id,
                    "name": p.name,
                    "status": p.status,
                    "approval_status": p.approval_status,
                    "verification_at_lead_from_mail": p.at_lead_time_email,
                        "rera_no": getattr(p, "rera_no", None),
                    "price_per_sqft": getattr(p, "price_per_sqft", None),
                })

            if unit_type:
                offering_qs = OfferingType.objects.filter(is_active=True).order_by("name")
                payload["offering_types"] = OfferingTypeSerializer(offering_qs, many=True).data

            return Response(payload, status=200)

        # ---- Full tree mode (projects + towers + floors [+ units]) ----
        floor_qs = Floor.objects.only("id", "number", "tower_id").order_by("number")
        if include_units:
            unit_qs = Unit.objects.only("id", "unit_no", "status", "floor_id").order_by("unit_no")
            floor_qs = floor_qs.prefetch_related(Prefetch("units", queryset=unit_qs))

        tower_qs = (
            Tower.objects.only("id", "name", "project_id")
            .prefetch_related(Prefetch("floors", queryset=floor_qs))
            .order_by("name")
        )

        projects = (
            project_qs
            .only("id", "name", "status", "approval_status", "price_per_sqft","rera_no")
            .prefetch_related(Prefetch("towers", queryset=tower_qs))
        )

               # ---- build tree response ----
        payload = {"admin_id": admin_id, "projects": []}
        for p in projects:
            p_item = {
                "id": p.id,
                "name": p.name,
                "status": p.status,
                "approval_status": p.approval_status,
                "price_per_sqft": getattr(p, "price_per_sqft", None),
        "rera_number": getattr(p, "rera_no", None),
"email_for_lead":getattr(p, "at_lead_time_email", None),
                "towers": [],
            }
            for t in p.towers.all():
                t_item = {"id": t.id, "name": t.name, "floors": []}
                for f in t.floors.all():
                    f_item = {"id": f.id, "number": f.number}
                    if include_units:
                        f_item["units"] = [
                            {
                                "id": uu.id,
                                "unit_no": uu.unit_no,
                                "status": uu.status,
                            }
                            for uu in f.units.all()
                        ]
                    t_item["floors"].append(f_item)
                p_item["towers"].append(t_item)
            payload["projects"].append(p_item)

        if unit_type:
            offering_qs = OfferingType.objects.filter(is_active=True).order_by("name")
            payload["offering_types"] = OfferingTypeSerializer(
                offering_qs, many=True
            ).data

        # ---- Add brand here for full tree response ----
        try:
            brand = ClientBrand.objects.get(admin_id=admin_id)
            payload["brand"] = ClientBrandSerializer(brand, context={"request": request}).data
        except ClientBrand.DoesNotExist:
            payload["brand"] = None

        return Response(payload, status=200)





class CreateBankAllInOneView(APIView):
    """
    POST /api/client/bank-setup/create-all/
    Body:
    {
      "bank":   {"code":"BNK001","name":"HDFC Bank","bank_type":1,"bank_category":2},   // code OR id (id overrides)
      "branch": {"branch_name":"Andheri","branch_code":"AND001","ifsc":"HDFC0001234","micr":"...","address":"...","contact_name":"...","contact_phone":"...","contact_email":"..."},
      "project_link": {"project":10,"apf_number":"APF-2025-01","status":"ACTIVE","product_ids":[1,3,5]}
    }
    Permissions: staff OR admin owning the project.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bank_data = request.data.get("bank") or {}
        branch_data = request.data.get("branch") or {}
        link = request.data.get("project_link") or {}

        # --- validate project & auth
        project_id = link.get("project")
        if not project_id:
            return Response({"detail": "project_link.project is required."}, status=400)
        project = get_object_or_404(Project, id=project_id)

        user = request.user
        if not (user.is_staff or (getattr(user, "role", None) == Role.ADMIN and project.belongs_to_id == user.id)):
            return Response({"detail": "Not allowed for this project."}, status=403)

        # --- upsert bank
        bank = None
        if "id" in bank_data and bank_data["id"]:
            bank = get_object_or_404(Bank, id=bank_data["id"])
        else:
            code = bank_data.get("code")
            if not code:
                return Response({"detail": "bank.code is required if bank.id not provided."}, status=400)
            bank, _created = Bank.objects.get_or_create(
                code=code,
                defaults={
                    "name": bank_data.get("name", ""),
                    "bank_type_id": bank_data.get("bank_type"),
                    "bank_category_id": bank_data.get("bank_category"),
                },
            )
            # update if optional fields provided
            updates = {}
            if "name" in bank_data: updates["name"] = bank_data["name"]
            if "bank_type" in bank_data: updates["bank_type_id"] = bank_data["bank_type"]
            if "bank_category" in bank_data: updates["bank_category_id"] = bank_data["bank_category"]
            if updates:
                for k, v in updates.items(): setattr(bank, k, v)
                bank.save(update_fields=list(updates.keys()))

        # --- upsert branch by IFSC or id
        if "id" in branch_data and branch_data["id"]:
            branch = get_object_or_404(BankBranch, id=branch_data["id"])
        else:
            ifsc = branch_data.get("ifsc")
            if not ifsc:
                return Response({"detail": "branch.ifsc is required if branch.id not provided."}, status=400)
            branch, created = BankBranch.objects.get_or_create(
                ifsc=ifsc,
                defaults={
                    "bank": bank,
                    "branch_name": branch_data.get("branch_name", ""),
                    "branch_code": branch_data.get("branch_code", ""),
                    "micr": branch_data.get("micr", ""),
                    "address": branch_data.get("address", ""),
                    "contact_name": branch_data.get("contact_name", ""),
                    "contact_phone": branch_data.get("contact_phone", ""),
                    "contact_email": branch_data.get("contact_email", ""),
                },
            )
            if not created:
                if branch.bank_id != bank.id:
                    return Response({"detail": "IFSC already linked to a different bank."}, status=400)
                updates = {}
                for fld in ("branch_name", "branch_code", "micr", "address", "contact_name", "contact_phone", "contact_email"):
                    if fld in branch_data:
                        updates[fld] = branch_data[fld]
                if updates:
                    for k, v in updates.items(): setattr(branch, k, v)
                    branch.save(update_fields=list(updates.keys()))

        # --- link to project + products
        pb, created = ProjectBank.objects.get_or_create(
            project=project, bank_branch=branch,
            defaults={"apf_number": link.get("apf_number", ""), "status": link.get("status", "ACTIVE")}
        )
        if not created:
            if "apf_number" in link: pb.apf_number = link["apf_number"]
            if "status" in link: pb.status = link["status"]
            pb.save()

        product_ids = link.get("product_ids") or []
        if product_ids:
            pb.products.all().delete()
            for pid in product_ids:
                ProjectBankProduct.objects.get_or_create(project_bank=pb, product_id=pid)

        return Response(
            {"bank_id": bank.id, "branch_id": branch.id, "project_bank_id": pb.id},
            status=201
        )

