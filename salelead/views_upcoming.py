# salelead/views_upcoming.py

from datetime import datetime, time as time_cls
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import SalesLead, SalesLeadUpdate, SiteVisit
from .views import IsAuthenticatedAndActive
from salelead.utils import _project_ids_for_user


def _normalize_date(val):
    """
    Ensure event_date is always a datetime.date (not datetime.datetime).
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    return val  # already date


def _normalize_time(val, fallback_dt=None):
    """
    Ensure event_time is always a datetime.time (or None).
    - If val is None and fallback_dt is datetime -> use fallback_dt.time()
    - If val is a string "HH:MM[:SS]" -> parse
    """
    if val is None and isinstance(fallback_dt, datetime):
        return fallback_dt.time().replace(microsecond=0)

    if val is None:
        return None

    if isinstance(val, datetime):
        return val.time().replace(microsecond=0)

    if isinstance(val, str):
        try:
            return time_cls.fromisoformat(val)
        except ValueError:
            return None

    # datetime.time has .replace()
    if hasattr(val, "replace"):
        return val.replace(microsecond=0)

    return None


class UpcomingLeadActivityAPIView(APIView):
    """
    GET /api/sales/upcoming-activity/?project_id=12

    Optional:
      - ?date_from=2025-12-10
      - ?date_to=2025-12-20

    Returns:
      [
        {
          "lead_id": 1,
          "lead_name": "Rahul Sharma",
          "project_id": 12,
          "project_name": "Deep Shikhar",
          "items": [
            {
              "kind": "UPDATE" | "SITE_VISIT",
              "id": 101,
              "event_date": "2025-12-11",
              "event_time": "14:30:00",
              "title": "Follow-up Call",
              "description": "Client asked for brochure",
              "raw_type": "CALL",
              "status": "PENDING",
            }
          ]
        }
      ]
    """

    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, *args, **kwargs):
        user = request.user

        # ---------------- project_id required ----------------
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response(
                {"detail": "project_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project_id = int(project_id)
        except ValueError:
            return Response(
                {"detail": "project_id must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------- check access to project ----------------
        project_ids = _project_ids_for_user(user)
        if project_id not in project_ids:
            return Response(
                {"detail": "You do not have access to this project."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---------------- date range: default today → future ----------------
        today = timezone.localdate()

        date_from_str = request.query_params.get("date_from")
        date_to_str = request.query_params.get("date_to")

        if date_from_str:
            try:
                date_from = datetime.fromisoformat(date_from_str).date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date_from, use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            date_from = today

        date_to = None
        if date_to_str:
            try:
                date_to = datetime.fromisoformat(date_to_str).date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date_to, use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ---------------- leads for this user + project ----------------
        leads_qs = (
            SalesLead.objects.select_related("project", "assign_to").filter(
                project_id=project_id,
                assign_to=user,  # <-- change if your assignment field differs
            )
        )

        lead_ids = list(leads_qs.values_list("id", flat=True))
        if not lead_ids:
            return Response([], status=status.HTTP_200_OK)

        # ---------------- SalesLeadUpdate (upcoming) ----------------
        # event_date can be DateField OR DateTimeField.
        event_field = SalesLeadUpdate._meta.get_field("event_date")
        is_dt = event_field.get_internal_type() == "DateTimeField"
        date_lookup = "event_date__date" if is_dt else "event_date"

        updates_qs = (
            SalesLeadUpdate.objects.select_related(
                "sales_lead",
                "sales_lead__project",
                "created_by",
                "activity_status",
            ).filter(
                sales_lead_id__in=lead_ids,
                **{f"{date_lookup}__gte": date_from},
            )
        )
        if date_to:
            updates_qs = updates_qs.filter(**{f"{date_lookup}__lte": date_to})

        # ---------------- SiteVisit (upcoming) ----------------
        visits_qs = (
            SiteVisit.objects.select_related("lead", "project", "created_by").filter(
                lead_id__in=lead_ids,
                scheduled_at__date__gte=date_from,
            )
        )
        if date_to:
            visits_qs = visits_qs.filter(scheduled_at__date__lte=date_to)

        # ---------------- base map per lead ----------------
        lead_map = {}
        for lead in leads_qs:
            lead_name = (
                getattr(lead, "full_name", None)
                or " ".join(
                    [
                        (getattr(lead, "first_name", "") or "").strip(),
                        (getattr(lead, "last_name", "") or "").strip(),
                    ]
                ).strip()
                or getattr(lead, "primary_contact_name", None)
                or f"Lead #{lead.id}"
            )

            project_name = getattr(lead.project, "name", None) or f"Project #{lead.project_id}"

            lead_map[lead.id] = {
                "lead_id": lead.id,
                "lead_name": lead_name,
                "project_id": lead.project_id,
                "project_name": project_name,
                "items": [],
            }

        def add_item(lead_id, item):
            if lead_id in lead_map:
                lead_map[lead_id]["items"].append(item)

        # ---------------- convert SalesLeadUpdate → items ----------------
        for u in updates_qs:
            title = getattr(u, "title", None)
            if not title:
                if hasattr(u, "get_update_type_display"):
                    title = u.get_update_type_display()
                else:
                    title = getattr(u, "update_type", "Update")

            description = (
                getattr(u, "description", None)
                or getattr(u, "notes", None)
                or getattr(u, "remark", None)
                or ""
            )

            status_label = None
            if getattr(u, "activity_status_id", None):
                status_label = (
                    getattr(u.activity_status, "name", None)
                    or getattr(u.activity_status, "code", None)
                    or str(u.activity_status_id)
                )

            raw_date = getattr(u, "event_date", None)   # may be date OR datetime
            raw_time = getattr(u, "event_time", None)   # may be time OR string OR None

            item = {
                "kind": "UPDATE",
                "id": u.id,
                "event_date": _normalize_date(raw_date),  # ✅ always date
                "event_time": _normalize_time(raw_time, fallback_dt=raw_date),
                "title": title,
                "description": description,
                "raw_type": getattr(u, "update_type", None),
                "status": status_label,
            }
            add_item(u.sales_lead_id, item)

        # ---------------- convert SiteVisit → items ----------------
        for v in visits_qs:
            dt = v.scheduled_at  # datetime

            if hasattr(v, "get_visit_type_display"):
                visit_title = v.get_visit_type_display()
            else:
                visit_title = getattr(v, "visit_type", "Site visit")

            description = (
                getattr(v, "outcome_notes", None)
                or getattr(v, "public_notes", None)
                or getattr(v, "internal_notes", None)
                or ""
            )

            if hasattr(v, "get_status_display"):
                status_label = v.get_status_display()
            else:
                status_label = getattr(v, "status", None)

            item = {
                "kind": "SITE_VISIT",
                "id": v.id,
                "event_date": dt.date(),  # date
                "event_time": dt.time().replace(microsecond=0),  # time
                "title": visit_title,
                "description": description,
                "raw_type": getattr(v, "visit_type", None),
                "status": status_label,
                "location_name": getattr(v, "location_name", None),
            }
            add_item(v.lead_id, item)

        # ---------------- sort items within each lead ----------------
        for lead_data in lead_map.values():
            lead_data["items"].sort(
                key=lambda x: (
                    x["event_date"] or timezone.localdate(),
                    x["event_time"] or time_cls.min,
                )
            )

        # final list
        data = list(lead_map.values())
        return Response(data, status=status.HTTP_200_OK)
