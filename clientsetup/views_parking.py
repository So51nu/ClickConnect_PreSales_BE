from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from django.db import transaction
from django.shortcuts import get_object_or_404
import json
import pandas as pd  
from .models import ParkingInventory, Project, Unit
from .serializers_parking import ParkingInventorySerializer, ParkingInventoryDetailSerializer
from .models import Project, Tower, ParkingInventory


class ParkingInventoryTreeAPIView(APIView):
    """
    GET /api/client/parking/tree/?project_id=<id>

    Returns:
    {
      "project": { "id": ..., "name": "..." },
      "towers": [
        {
          "id": ..., "name": "...",
          "parkings": [
            {
              "id": ...,
              "slot_label": "B1-12",
              "rera_slot_no": "PARK-123",
              "parking_type": "OPEN",
              "level_label": "Basement-1",
              "area_sqft": "120.00",
              "status": "ACTIVE",
              "availability_status": "AVAILABLE",
              "reserved_for_unit": {
                "id": ...,
                "unit_no": "903"
              } | null
            },
            ...
          ]
        },
        ...
      ],
      "no_tower": [ ... ]   # tower=null wale slots
    }
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "project_id is required."}, status=400)

        project = get_object_or_404(Project, pk=project_id)

        towers_qs = Tower.objects.filter(project_id=project.id).order_by("id")

        parking_qs = (
            ParkingInventory.objects
            .filter(project_id=project.id)
            .select_related("tower", "reserved_for_unit")
            .order_by("slot_label")
        )

        # tower_id -> [parking...]
        parkings_by_tower = {}
        no_tower_list = []
        for p in parking_qs:
            if p.tower_id:
                parkings_by_tower.setdefault(p.tower_id, []).append(p)
            else:
                no_tower_list.append(p)

        data = {
            "project": {
                "id": project.id,
                "name": getattr(project, "name", str(project)),
            },
            "towers": [],
            "no_tower": [],
        }

        for t in towers_qs:
            tower_block = {
                "id": t.id,
                "name": getattr(t, "name", f"Tower {t.id}"),
                "parkings": [],
            }

            for p in parkings_by_tower.get(t.id, []):
                tower_block["parkings"].append({
                    "id": p.id,
                    "slot_label": p.slot_label,
                    "block_label": p.block_label,
                    "slot_number": p.slot_number,
                    "parking_type": p.parking_type,
                    "vehicle_type": p.vehicle_type,
                    "usage_type": p.usage_type,
                    "is_ev_ready": p.is_ev_ready,
                    "is_accessible": p.is_accessible,
                    "level_label": p.level_label,
                    "status": p.status,
                    "availability_status": p.availability_status,
                    "rera_slot_no": p.rera_slot_no,
                    "area_sqft": p.area_sqft,
                    "reserved_for_unit": (
                        {
                            "id": p.reserved_for_unit_id,
                            "unit_no": getattr(p.reserved_for_unit, "unit_no", None),
                        }
                        if p.reserved_for_unit_id else None
                    ),
                })
            data["towers"].append(tower_block)

        # tower=null group
        for p in no_tower_list:
            data["no_tower"].append({
                "id": p.id,
                "slot_label": p.slot_label,
                "rera_slot_no": p.rera_slot_no,
                "parking_type": p.parking_type,
                "level_label": p.level_label,
                "area_sqft": p.area_sqft,
                "status": p.status,
                "availability_status": p.availability_status,
                "reserved_for_unit": (
                    {
                        "id": p.reserved_for_unit_id,
                        "unit_no": getattr(p.reserved_for_unit, "unit_no", None),
                    }
                    if p.reserved_for_unit_id else None
                ),
            })

        return Response(data, status=200)



class ParkingInventoryViewSet(viewsets.ModelViewSet):
    """
    Endpoints:
      - GET    /api/client/parking/?project_id=...
      - POST   /api/client/parking/
      - POST   /api/client/parking/bulk-create/
      - PATCH  /api/client/parking/{id}/
      - PUT    /api/client/parking/{id}/
      - GET    /api/client/parking/{id}/
      - DELETE /api/client/parking/{id}/

      Extra:
      - GET    /api/client/parking/by-unit/?unit_id=...
      - GET    /api/client/parking/available/?project_id=...&tower_id=...
    """

    queryset = ParkingInventory.objects.select_related(
        "project", "tower", "floor", "reserved_for_unit"
    ).all()
    serializer_class = ParkingInventorySerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params

        project_id = q.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)

        tower_id = q.get("tower_id")
        if tower_id:
            qs = qs.filter(tower_id=tower_id)

        # ✅ floor-wise filter (badi parking me useful)
        floor_id = q.get("floor_id")
        if floor_id:
            qs = qs.filter(floor_id=floor_id)

        availability = q.get("availability_status")
        if availability:
            qs = qs.filter(availability_status=availability)

        status_val = q.get("status")
        if status_val:
            qs = qs.filter(status=status_val)

        parking_type = q.get("parking_type")
        if parking_type:
            qs = qs.filter(parking_type=parking_type)

        # ✅ vehicle / usage filters
        vehicle_type = q.get("vehicle_type")
        if vehicle_type:
            qs = qs.filter(vehicle_type=vehicle_type)

        usage_type = q.get("usage_type")
        if usage_type:
            qs = qs.filter(usage_type=usage_type)

        # ✅ flags: EV / accessible
        def _parse_bool(val: str | None):
            if val is None:
                return None
            v = val.strip().lower()
            if v in ["1", "true", "yes", "y", "on"]:
                return True
            if v in ["0", "false", "no", "n", "off"]:
                return False
            return None

        is_ev_ready = _parse_bool(q.get("is_ev_ready"))
        if is_ev_ready is not None:
            qs = qs.filter(is_ev_ready=is_ev_ready)

        is_accessible = _parse_bool(q.get("is_accessible"))
        if is_accessible is not None:
            qs = qs.filter(is_accessible=is_accessible)

        reserved_for_unit = q.get("reserved_for_unit_id")
        if reserved_for_unit:
            qs = qs.filter(reserved_for_unit_id=reserved_for_unit)

        # ✅ RERA + block/slot based search
        rera_slot_no = q.get("rera_slot_no")
        if rera_slot_no:
            qs = qs.filter(rera_slot_no__icontains=rera_slot_no)

        block_label = q.get("block_label")
        if block_label:
            qs = qs.filter(block_label__iexact=block_label)

        slot_number = q.get("slot_number")
        if slot_number:
            qs = qs.filter(slot_number__iexact=slot_number)

        return qs.order_by("slot_label")

    # ---------- BULK CREATE (JSON + optional Excel) ----------
    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """
        Bulk create parking inventory.

        Supports:
        1) JSON array body
        2) multipart with "items" JSON
        3) Excel file upload: multipart with "file" = .xlsx

        Excel expected columns example:

        Required:
        - project_id
        - slot_label  (ya block_label + slot_number)

        Optional / recommended:
        - tower_id
        - floor_id
        - block_label
        - slot_number
        - parking_type          (OPEN / COVERED / STILT / PODIUM / OTHER)
        - level_label
        - vehicle_type          (TWO_WHEELER / FOUR_WHEELER / BOTH)
        - usage_type            (RESIDENT / VISITOR / STAFF / COMMERCIAL)
        - is_ev_ready           (1/0, TRUE/FALSE, Yes/No)
        - is_accessible         (1/0, TRUE/FALSE, Yes/No)
        - rera_slot_no
        - rera_parking_type
        - area_sqft
        - reserved_for_unit_id
        - status                (DRAFT / ACTIVE / INACTIVE)
        - availability_status   (AVAILABLE / BOOKED / BLOCKED)
        - remarks
        """
        raw = request.data

        excel_file = request.FILES.get("file") or request.FILES.get("excel")
        if excel_file:
            # CASE 3: Excel
            try:
                df = pd.read_excel(excel_file)
            except Exception as e:
                return Response(
                    {"detail": f"Failed to read Excel: {e}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # optional renaming if Excel headers different
            rename_map = {
                "project_id": "project",
                "tower_id": "tower",
                "floor_id": "floor",
                "reserved_for_unit_id": "reserved_for_unit",
            }
            df.rename(columns=rename_map, inplace=True)
            df = df.where(df.notnull(), None)

            items = df.to_dict(orient="records")
        elif isinstance(raw, list):
            # CASE 1: pure JSON array
            items = raw
        else:
            # CASE 2: multipart with items JSON
            items_json = raw.get("items")
            if not items_json:
                return Response(
                    {"detail": 'Expected a JSON list, "items" field, or Excel "file".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                items = json.loads(items_json)
            except json.JSONDecodeError:
                return Response(
                    {"detail": 'Invalid JSON in "items".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if not isinstance(items, list):
            return Response({"detail": "Items must be a list."}, status=400)

        created = []
        errors = []

        def _parse_bool(val):
            if val is None:
                return None
            if isinstance(val, bool):
                return val
            v = str(val).strip().lower()
            if v in ["1", "true", "yes", "y"]:
                return True
            if v in ["0", "false", "no", "n"]:
                return False
            return None

        with transaction.atomic():
            for idx, payload in enumerate(items, start=1):
                payload = dict(payload)

                # FK cleanup: project/tower/floor/reserved_for_unit
                for fk_field in ["project", "tower", "floor", "reserved_for_unit"]:
                    val = payload.get(fk_field)
                    if val in ("", None):
                        payload[fk_field] = None
                    else:
                        try:
                            payload[fk_field] = int(val)
                        except (ValueError, TypeError):
                            pass

                # Normalize choice fields to UPPERCASE (optional but handy)
                for choice_field in [
                    "parking_type",
                    "vehicle_type",
                    "usage_type",
                    "status",
                    "availability_status",
                ]:
                    val = payload.get(choice_field)
                    if isinstance(val, str):
                        payload[choice_field] = val.strip().upper()

                # Boolean fields from Excel
                for bool_field in ["is_ev_ready", "is_accessible"]:
                    parsed = _parse_bool(payload.get(bool_field))
                    if parsed is not None:
                        payload[bool_field] = parsed

                ser = ParkingInventorySerializer(
                    data=payload, context={"request": request}
                )
                if ser.is_valid():
                    obj = ser.save()
                    created.append(obj.id)
                else:
                    errors.append({"index": idx, "errors": ser.errors})

        code = (
            status.HTTP_201_CREATED
            if created and not errors
            else status.HTTP_207_MULTI_STATUS
        )
        return Response({"created_ids": created, "errors": errors}, status=code)

    # ---------- BY UNIT (reserved + other available) ----------
    @action(detail=False, methods=["get"], url_path="by-unit")
    def by_unit(self, request):
        """
        GET /api/client/parking/by-unit/?unit_id=<id>&project_id=<pid>&tower_id=<tid>

        - reserved_slots: jo reserved_for_unit = unit_id hai
        - available_slots: same project (and optional tower), AVAILABLE slots
        """
        unit_id = request.query_params.get("unit_id")
        project_id = request.query_params.get("project_id")

        if not unit_id:
            return Response(
                {"detail": "unit_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unit = get_object_or_404(Unit, pk=unit_id)

        if not project_id:
            project_id = unit.project_id

        tower_id = request.query_params.get("tower_id")

        base_qs = ParkingInventory.objects.filter(project_id=project_id)

        if tower_id:
            base_qs = base_qs.filter(tower_id=tower_id)

        # (optional) agar sirf RESIDENT slots chahiye hon to:
        # usage_type = request.query_params.get("usage_type")
        # if usage_type:
        #     base_qs = base_qs.filter(usage_type=usage_type)

        reserved_qs = base_qs.filter(reserved_for_unit=unit)
        available_qs = base_qs.filter(
            availability_status=AvailabilityStatus.AVAILABLE
        ).exclude(reserved_for_unit=unit)

        data = {
            "reserved_slots": ParkingInventorySerializer(
                reserved_qs, many=True, context={"request": request}
            ).data,
            "available_slots": ParkingInventorySerializer(
                available_qs, many=True, context={"request": request}
            ).data,
        }
        return Response(data, status=status.HTTP_200_OK)

    # ---------- SIMPLE AVAILABLE LIST ----------
    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        """
        GET /api/client/parking/available/?project_id=...&tower_id=...&vehicle_type=...&usage_type=...

        Sirf AVAILABLE parking slots return karega.
        Baaki saare filters get_queryset() se aa jayenge (project/tower/floor/vehicle/usage/EV etc.)
        """
        qs = self.get_queryset().filter(availability_status=AvailabilityStatus.AVAILABLE)
        serializer = ParkingInventorySerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

