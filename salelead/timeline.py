# salelead/timeline.py

from decimal import Decimal
from typing import List, Dict, Any
from datetime import datetime, date, time, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date

from salelead.models import (
    SalesLead,
    SalesLeadStatusHistory,
    SalesLeadUpdate,
    SalesLeadUpdateStatusHistory,
    SalesLeadStageHistory,
    SalesLeadEmailLog,
    LeadComment,
    SiteVisit,
    SiteVisitRescheduleHistory,
    PaymentLead,
)
from booking.models import Booking
from costsheet.models import CostSheet


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _ensure_datetime(value):
    """
    Ensure we always work with a timezone-aware datetime.

    - If value is datetime: make it aware (if needed)
    - If value is date: convert to datetime at midnight, then make aware
    - Otherwise: return as-is (caller can decide)
    """
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            try:
                return timezone.make_aware(value, timezone.get_current_timezone())
            except Exception:
                # If something goes wrong, at least return original
                return value
        return value

    if isinstance(value, date):
        dt = datetime.combine(value, time.min)
        return timezone.make_aware(dt, timezone.get_current_timezone())

    return value

def _ts(obj, *candidates):
    """
    Safe timestamp picker.

    - Tries the explicit field names given in *candidates
    - Fallback to created_at / updated_at
    - Final fallback: timezone.now()

    Always returns a timezone-aware datetime.
    """
    for name in candidates:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value:
                return _ensure_datetime(value)

    for fallback in ("created_at", "updated_at"):
        if hasattr(obj, fallback):
            value = getattr(obj, fallback)
            if value:
                return _ensure_datetime(value)

    # final fallback
    return timezone.now()



def _decimal_to_str(value):
    if isinstance(value, Decimal):
        return str(value)
    return value


# -------------------------------------------------------------------
# Main builder
# -------------------------------------------------------------------


def build_lead_timeline(lead: SalesLead) -> List[Dict[str, Any]]:
    """
    Ek lead ka consolidated timeline list (Python list of dicts).
    Isko View me sort + paginate karke response me bhejna hai.

    Har item ka structure roughly:

    {
        "id": "...",
        "object_type": "BOOKING" / "PAYMENT" / "LEAD_STATUS" / ...,
        "timestamp": datetime,
        "title": "Short title",
        "description": "Optional description / note",
        "meta": {... extra fields ...}
    }
    """

    events: List[Dict[str, Any]] = []

    # ---------------- 1) Lead Status History ----------------
    # Model has FK: sales_lead, NOT 'lead'
    for obj in SalesLeadStatusHistory.objects.filter(
        sales_lead=lead
    ).select_related("old_status", "new_status", "changed_by"):
        ts = _ts(obj, "event_date", "changed_at")

        old_label = str(obj.old_status) if getattr(obj, "old_status", None) else None
        new_label = str(obj.new_status) if getattr(obj, "new_status", None) else None

        events.append(
            {
                "id": f"lead_status_{obj.id}",
                "object_type": "LEAD_STATUS",
                "timestamp": ts,
                "title": f"Status changed to {new_label or ''}",
                # model field is `comment`, not `note`
                "description": getattr(obj, "comment", "") or "",
                "meta": {
                    "old_status": old_label,
                    "new_status": new_label,
                    "changed_by": (
                        getattr(
                            getattr(obj, "changed_by", None),
                            "get_full_name",
                            lambda: None,
                        )()
                        if getattr(obj, "changed_by", None)
                        else None
                    ),
                },
            }
        )

        # ---------------- 2b) Lead Updates (FOLLOW_UP / NOTE / CALL / etc.) ----------------
    for obj in SalesLeadUpdate.objects.filter(
        sales_lead=lead
    ).select_related("activity_status", "created_by"):
        ts = _ts(obj, "event_date")

        creator = getattr(obj, "created_by", None)
        creator_name = (
            getattr(creator, "get_full_name", lambda: None)() if creator else None
        )

        status_obj = getattr(obj, "activity_status", None)
        status_name = getattr(status_obj, "name", None) if status_obj else None

        events.append(
            {
                "id": f"lead_update_{obj.id}",
                "object_type": "LEAD_UPDATE",  # 👈 high-level type
                "timestamp": ts,
                "title": obj.title or f"{obj.update_type.title()} update",
                "description": obj.info or "",
                "meta": {
                    "update_id": obj.id,
                    "update_type": obj.update_type,          # FOLLOW_UP / NOTE / CALL / ...
                    "activity_status": status_name,          # from SalesLeadUpdateStatus
                    "created_by": creator_name,
                    "event_date": obj.event_date,
                },
            }
        )


    # ---------------- 2) Lead Update Status History ----------------
    # Model has FK: sales_lead_update → SalesLeadUpdate
    # and SalesLeadUpdate has FK sales_lead → SalesLead.
    for obj in SalesLeadUpdateStatusHistory.objects.filter(
        sales_lead_update__sales_lead=lead
    ).select_related("sales_lead_update", "changed_by", "old_status", "new_status"):
        ts = _ts(obj, "event_date")

        old_label = str(obj.old_status) if getattr(obj, "old_status", None) else None
        new_label = str(obj.new_status) if getattr(obj, "new_status", None) else None

        events.append(
            {
                "id": f"lead_update_status_{obj.id}",
                "object_type": "LEAD_UPDATE_STATUS",
                "timestamp": ts,
                "title": "Follow-up / update status changed",
                "description": getattr(obj, "comment", "") or "",
                "meta": {
                    "update_id": getattr(obj, "sales_lead_update_id", None),
                    "old_status": old_label,
                    "new_status": new_label,
                    "changed_by": (
                        getattr(
                            getattr(obj, "changed_by", None),
                            "get_full_name",
                            lambda: None,
                        )()
                        if getattr(obj, "changed_by", None)
                        else None
                    ),
                },
            }
        )

    # ---------------- 3) Stage History ----------------
    for obj in SalesLeadStageHistory.objects.filter(
        sales_lead=lead
    ).select_related("stage", "status", "sub_status", "created_by"):
        ts = _ts(obj, "event_date")
        stage_obj = getattr(obj, "stage", None)
        status_obj = getattr(obj, "status", None)
        sub_status_obj = getattr(obj, "sub_status", None)

        stage_name = getattr(stage_obj, "name", None)
        status_name = getattr(status_obj, "name", None)
        sub_status_name = getattr(sub_status_obj, "name", None)

        events.append(
            {
                "id": f"stage_{obj.id}",
                "object_type": "LEAD_STAGE",
                "timestamp": ts,
                "title": f"Stage changed to {stage_name or ''}",
                "description": getattr(obj, "notes", "") or "",
                "meta": {
                    "stage_id": getattr(obj, "stage_id", None),
                    "stage_name": stage_name,
                    "status_name": status_name,
                    "sub_status_name": sub_status_name,
                    "changed_by": (
                        getattr(
                            getattr(obj, "created_by", None),
                            "get_full_name",
                            lambda: None,
                        )()
                        if getattr(obj, "created_by", None)
                        else None
                    ),
                },
            }
        )

    # ---------------- 4) Email Logs ----------------
    for obj in SalesLeadEmailLog.objects.filter(sales_lead=lead):
        ts = _ts(obj, "sent_at")

        events.append(
            {
                "id": f"email_{obj.id}",
                "object_type": "EMAIL",
                "timestamp": ts,
                "title": getattr(obj, "subject", "") or "Email sent",
                "description": (
                    getattr(obj, "body_preview", "")[:200]
                    if hasattr(obj, "body_preview")
                    else ""
                ),
                "meta": {
                    "to": getattr(obj, "to", None),
                    "status": getattr(obj, "status", None),
                },
            }
        )

    # ---------------- 5) Comments ----------------
    for obj in LeadComment.objects.filter(
        sales_lead=lead
    ).select_related("created_by"):
        ts = _ts(obj, "created_at")
        creator = getattr(obj, "created_by", None)
        creator_name = (
            getattr(creator, "get_full_name", lambda: None)() if creator else None
        )

        events.append(
            {
                "id": f"comment_{obj.id}",
                "object_type": "COMMENT",
                "timestamp": ts,
                "title": f"Comment by {creator_name or 'User'}",
                "description": getattr(obj, "text", "")
                or getattr(obj, "comment", "")
                or "",
                "meta": {
                    "created_by": creator_name,
                },
            }
        )

    # ---------------- 6) Site Visits ----------------
    for obj in SiteVisit.objects.filter(lead=lead).select_related("project"):
        ts = _ts(obj, "scheduled_at")
        project_obj = getattr(obj, "project", None)

        events.append(
            {
                "id": f"site_visit_{obj.id}",
                "object_type": "SITE_VISIT",
                "timestamp": ts,
                "title": f"Site visit ({obj.get_status_display()})"
                if hasattr(obj, "get_status_display")
                else "Site visit",
                "description": f"Scheduled at {obj.scheduled_at}",
                "meta": {
                    "visit_id": obj.id,
                    "status": getattr(obj, "status", None),
                    "visit_type": getattr(obj, "visit_type", None),
                    "project": getattr(project_obj, "name", None),
                    "member_name": getattr(obj, "member_name", None),
                    "member_mobile": getattr(obj, "member_mobile_number", None),
                },
            }
        )

    # ---------------- 7) Site Visit Reschedule History ----------------
    for obj in SiteVisitRescheduleHistory.objects.filter(
        site_visit__lead=lead          # 👈 FIXED: was visit__lead
    ).select_related("site_visit", "created_by"):
        ts = _ts(obj, "created_at")

        events.append(
            {
                "id": f"site_visit_reschedule_{obj.id}",
                "object_type": "SITE_VISIT_RESCHEDULE",
                "timestamp": ts,
                "title": "Site visit rescheduled",
                "description": getattr(obj, "reason", "") or "",
                "meta": {
                    "visit_id": getattr(obj, "site_visit_id", None),  # 👈 use site_visit_id
                    "old_scheduled_at": getattr(obj, "old_scheduled_at", None),
                    "new_scheduled_at": getattr(obj, "new_scheduled_at", None),
                    "created_by": (
                        getattr(
                            getattr(obj, "created_by", None),
                            "get_full_name",
                            lambda: None,
                        )()
                        if getattr(obj, "created_by", None)
                        else None
                    ),
                },
            }
        )

    # ---------------- 8) Payments ----------------
    for obj in PaymentLead.objects.filter(lead=lead).select_related(
        "project", "booking"
    ):
        ts = _ts(obj, "payment_date")
        events.append(
            {
                "id": f"payment_{obj.id}",
                "object_type": "PAYMENT",
                "timestamp": ts,
                "title": f"{obj.payment_type} payment – ₹{_decimal_to_str(obj.amount)}",
                "description": f"Method: {obj.payment_method}, Status: {obj.status}",
                "meta": {
                    "payment_id": obj.id,
                    "type": getattr(obj, "payment_type", None),
                    "method": getattr(obj, "payment_method", None),
                    "status": getattr(obj, "status", None),
                    "amount": _decimal_to_str(getattr(obj, "amount", None)),
                    "booking_id": getattr(obj, "booking_id", None),
                },
            }
        )

    # ---------------- 9) Cost Sheets ----------------
    for obj in CostSheet.objects.filter(lead=lead).select_related("project"):
        ts = _ts(obj, "date")
        events.append(
            {
                "id": f"cost_sheet_{obj.id}",
                "object_type": "COST_SHEET",
                "timestamp": ts,
                "title": f"Cost Sheet {obj.quotation_no}",
                "description": (
                    f"Status: {getattr(obj, 'status_label', None) or getattr(obj, 'status', '')}, "
                    f"Net: {getattr(obj, 'net_payable_amount', '')}"
                ),
                "meta": {
                    "cost_sheet_id": obj.id,
                    "quotation_no": getattr(obj, "quotation_no", None),
                    "status": getattr(obj, "status", None),
                    "status_label": getattr(obj, "status_label", None),
                    "date": getattr(obj, "date", None),
                    "net_payable_amount": _decimal_to_str(
                        getattr(obj, "net_payable_amount", None)
                    ),
                    "unit_no": getattr(obj, "unit_no", None),
                },
            }
        )

    # ---------------- 10) Bookings ----------------
    for obj in Booking.objects.filter(sales_lead=lead).select_related(
        "unit", "project"
    ):
        ts = _ts(obj, "booking_date", "booked_at", "blocked_at")
        project_obj = getattr(obj, "project", None)
        unit_obj = getattr(obj, "unit", None)

        unit_label = str(unit_obj) if obj.unit_id else ""

        events.append(
            {
                "id": f"booking_{obj.id}",
                "object_type": "BOOKING",
                "timestamp": ts,
                "title": f"Booking created – {unit_label}",
                "description": (
                    f"Status: {getattr(obj, 'status_label', '')}, "
                    f"Booking Date: {getattr(obj, 'booking_date', '')}"
                ),
                "meta": {
                    "booking_id": obj.id,
                    "status": getattr(obj, "status", None),
                    "status_label": getattr(obj, "status_label", None),
                    "booking_date": getattr(obj, "booking_date", None),
                    "agreement_value": _decimal_to_str(
                        getattr(obj, "agreement_value", None)
                    ),
                    "project": getattr(project_obj, "name", None),
                    "unit_id": getattr(obj, "unit_id", None),
                },
            }
        )

    # --------------- FINAL: sort desc by timestamp ---------------
    events = [e for e in events if e.get("timestamp")]
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events


# -------------------------------------------------------------------
# Filtering helper for the API
# -------------------------------------------------------------------


def filter_timeline_events(events, request):
    """
    Query params:

      - types=BOOKING,PAYMENT,SITE_VISIT,LEAD_CHANGE   (comma separated, UPPERCASE)
      - from_date=YYYY-MM-DD
      - to_date=YYYY-MM-DD
      - q=free text
    """

    types_param = request.query_params.get("types")
    from_param = request.query_params.get("from_date")
    to_param = request.query_params.get("to_date")
    q_param = (request.query_params.get("q") or "").strip()

    # ---------- 1) type filter ----------
    type_set = None
    if types_param:
        type_set = {
            t.strip().upper()
            for t in types_param.split(",")
            if t.strip()
        }

    # ---------- 2) date range filter ----------
    start_dt = None
    end_dt = None

    if from_param:
        d = parse_date(from_param)
        if d:
            start_dt = timezone.make_aware(
                datetime.combine(d, time.min),
                timezone.get_current_timezone(),
            )

    if to_param:
        d = parse_date(to_param)
        if d:
            # inclusive end-date => next day 00:00 se strictly chhota
            end_dt = timezone.make_aware(
                datetime.combine(d + timedelta(days=1), time.min),
                timezone.get_current_timezone(),
            )

    # ---------- 3) keyword search ----------
    q_lower = q_param.lower() if q_param else ""

    filtered = []
    for ev in events:
        ts = ev.get("timestamp")
        if not ts:
            continue

        obj_type = ev.get("object_type")
        ts = _ensure_datetime(ts)
        # type filter
        if type_set is not None:
            if obj_type not in type_set:
                # LEAD_CHANGE is alias for all lead-related changes
                if (
                    "LEAD_CHANGE" in type_set
                    and obj_type
                    in {"LEAD_STATUS", "LEAD_UPDATE_STATUS", "LEAD_STAGE"}
                ):
                    pass
                else:
                    continue

        # date from
        if start_dt and ts < start_dt:
            continue

        # date to (inclusive)
        if end_dt and ts >= end_dt:
            continue

        # keyword filter
        if q_lower:
            title = (ev.get("title") or "").lower()
            desc = (ev.get("description") or "").lower()
            if q_lower not in title and q_lower not in desc:
                continue

        filtered.append(ev)

    return filtered
