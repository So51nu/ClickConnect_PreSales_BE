# dashboard/views.py

import logging
from datetime import timedelta

from django.db.models import Count, Sum, Avg, Max, Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from accounts.models import User, Role
from clientsetup.models import Project, Unit, Inventory
from salelead.models import (
    SalesLead,
    SalesLeadStageHistory,
    SiteVisit,
    SalesLeadUpdate,
)
from booking.models import Booking, BookingKycRequest
from costsheet.models import CostSheet, CostSheetAppliedOffer

logger = logging.getLogger(__name__)


# =====================================================
# Role / Ownership helpers (LOCAL TO THIS FILE)
# =====================================================
# =====================================================
# Role / Ownership helpers (FIXED & SAFE)
# =====================================================

def get_role_code(user):
    """
    Normalize role value.
    Works if user.role is:
    - string ("ADMIN")
    - Role model (role.code)
    """
    role = getattr(user, "role", None)

    if not role:
        return None

    if isinstance(role, str):
        return role.upper()

    return getattr(role, "code", None)


def get_effective_admin(user):
    """
    ADMIN        → self
    FULL_CONTROL → linked admin
    SALES/OTHER  → linked admin
    STAFF        → None (means no filtering)
    """
    if not user or not user.is_authenticated:
        return None

    if user.is_staff:
        return None

    role_code = get_role_code(user)

    if role_code == "ADMIN":
        return user

    if role_code == "FULL_CONTROL":
        return getattr(user, "admin", None)

    return getattr(user, "admin", None)


def is_admin_like(user):
    """
    ADMIN + FULL_CONTROL + staff
    Used ONLY for dashboard routing
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_staff:
        return True

    role_code = get_role_code(user)
    return role_code in ("ADMIN", "FULL_CONTROL")

# =====================================================
# Helper functions
# =====================================================

def get_date_range(request):
    """
    Query params:
      ?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD

    Defaults: last 30 days.
    Returns: (from_date, to_date) as date objects.
    """
    from_str = request.query_params.get("from_date")
    to_str = request.query_params.get("to_date")

    from_date = parse_date(from_str) if from_str else None
    to_date = parse_date(to_str) if to_str else None

    today = timezone.now().date()

    if not from_date and not to_date:
        to_date = today
        from_date = today - timedelta(days=30)
    elif from_date and not to_date:
        to_date = today
    elif to_date and not from_date:
        from_date = to_date - timedelta(days=30)

    # Safety: if from > to, swap
    if from_date and to_date and from_date > to_date:
        from_date, to_date = to_date, from_date

    return from_date, to_date


def apply_date_filter_dt(qs, field_name, from_date, to_date):
    """
    For DateTime fields: filter by date range on the date part.
    """
    if from_date:
        qs = qs.filter(**{f"{field_name}__date__gte": from_date})
    if to_date:
        qs = qs.filter(**{f"{field_name}__date__lte": to_date})
    return qs


def apply_date_filter_date(qs, field_name, from_date, to_date):
    """
    For Date fields: filter by date range.
    """
    if from_date:
        qs = qs.filter(**{f"{field_name}__gte": from_date})
    if to_date:
        qs = qs.filter(**{f"{field_name}__lte": to_date})
    return qs
def get_user_projects(user):
    """
    FINAL, SAFE, NON-BREAKING logic
    Works for ADMIN and FULL_CONTROL equally
    """
    qs = Project.objects.all()

    # Staff sees everything
    if user.is_staff:
        return qs

    admin_user = get_effective_admin(user)

    if admin_user:
        return qs.filter(belongs_to=admin_user)

    return qs.none()


def get_filtered_project_ids(request, user):
    """
    1) Get allowed projects for user.
    2) If ?projects=1,2 is passed, restrict to those IDs (intersection).
    Returns a list of project IDs.
    """
    allowed_qs = get_user_projects(user)

    param = request.query_params.get("projects")
    if param:
        try_ids = []
        for part in param.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                try_ids.append(int(part))
            except ValueError:
                # ignore invalid
                continue
        if try_ids:
            allowed_qs = allowed_qs.filter(id__in=try_ids)

    return list(allowed_qs.values_list("id", flat=True).distinct())


# =====================================================
# Admin Dashboard
# =====================================================

def build_admin_dashboard(user, project_ids, from_date, to_date):
    """
    Build admin dashboard JSON for given projects + date range.
    Safe to call inside a try/except in the view.
    """
    result = {
        "project_overview": {
            "total_projects": 0,
            "by_status": {},
        },
        "inventory": {
            "units": {
                "total_units": 0,
                "by_unit_status": {},
            },
            "availability": {},
        },
        "leads": {
            "new_leads": 0,
            "by_source": {},
            "by_stage": {},
            "by_classification": {},
            "cp_vs_non_cp": {
                "channel_partner": 0,
                "walkin": 0,
                "others": 0,
            },
        },
        "site_visits": {
            "upcoming": 0,
            "last_period": {},
        },
        "cost_sheets": {
            "count_by_status": {},
            "pipeline_value": {
                "sent_total": 0,
                "accepted_total": 0,
            },
            "offers": {
                "total_discount": 0,
                "costsheets_with_offers": 0,
            },
        },
        "bookings": {
            "count": 0,
            "total_agreement_value": 0,
            "by_status": {},
        },
        "kyc": {
            "requests_by_status": {},
            "avg_amount": 0,
        },
        "channel_partners": {
            "cp_summary": [],
            "top_cps_by_value": [],
        },
    }

    if not project_ids:
        # No projects available for this user
        return result

    # ---------------- Project overview ----------------
    project_qs = Project.objects.filter(id__in=project_ids)
    result["project_overview"]["total_projects"] = project_qs.count()
    status_rows = project_qs.values("status").annotate(count=Count("id"))
    by_status = {}
    for row in status_rows:
        status_key = row["status"] or "UNKNOWN"
        by_status[status_key] = row["count"]
    result["project_overview"]["by_status"] = by_status

    # ---------------- Inventory & Units (fully from Inventory) ----------------
    inv_qs = Inventory.objects.filter(project_id__in=project_ids)

    # total_units = total inventory rows (business inventory)
    total_units = inv_qs.count()
    result["inventory"]["units"]["total_units"] = total_units

    # by_unit_status - from Inventory.unit_status
    unit_status_rows = (
        inv_qs.values("unit_status")
        .annotate(count=Count("id"))
    )
    unit_status_map = {}
    for row in unit_status_rows:
        key = row["unit_status"] or "UNKNOWN"
        unit_status_map[key] = row["count"]
    result["inventory"]["units"]["by_unit_status"] = unit_status_map

    # availability - from Inventory.availability_status
    availability_rows = (
        inv_qs.values("availability_status")
        .annotate(count=Count("id"), value=Sum("total_cost"))
    )
    availability_map = {}
    for row in availability_rows:
        key = row["availability_status"] or "UNKNOWN"
        availability_map[key] = {
            "count": row["count"],
            "value": row["value"] or 0,
        }
    result["inventory"]["availability"] = availability_map

    # ---------------- Leads ----------------
    lead_qs = SalesLead.objects.filter(project_id__in=project_ids)
    lead_period_qs = apply_date_filter_dt(lead_qs, "created_at", from_date, to_date)

    result["leads"]["new_leads"] = lead_period_qs.count()

    # by_source (simple: just main source)
    source_rows = (
        lead_period_qs.values("source__name")
        .annotate(count=Count("id"))
        .order_by()
    )
    by_source = {}
    for row in source_rows:
        key = row["source__name"] or "Unknown"
        by_source[key] = row["count"]
    result["leads"]["by_source"] = by_source

    # by_classification
    classification_rows = (
        lead_qs.values("classification__name")
        .annotate(count=Count("id"))
        .order_by()
    )
    by_classification = {}
    for row in classification_rows:
        key = row["classification__name"] or "Unclassified"
        by_classification[key] = row["count"]
    result["leads"]["by_classification"] = by_classification

    # by_stage: latest stage per lead
    latest_stage_ids = (
        SalesLeadStageHistory.objects.filter(sales_lead__project_id__in=project_ids)
        .values("sales_lead_id")
        .annotate(last_id=Max("id"))
        .values_list("last_id", flat=True)
    )
    stage_qs = SalesLeadStageHistory.objects.filter(id__in=list(latest_stage_ids))
    stage_rows = stage_qs.values("stage__name").annotate(count=Count("id"))
    by_stage = {}
    for row in stage_rows:
        key = row["stage__name"] or "Unknown"
        by_stage[key] = row["count"]
    result["leads"]["by_stage"] = by_stage

    # cp_vs_non_cp
    cp_leads_count = lead_qs.filter(channel_partner__isnull=False).count()
    walkin_leads_count = lead_qs.filter(walking=True).count()
    others_count = lead_qs.count() - cp_leads_count - walkin_leads_count

    result["leads"]["cp_vs_non_cp"] = {
        "channel_partner": cp_leads_count,
        "walkin": walkin_leads_count,
        "others": max(0, others_count),
    }

    # ---------------- Site visits ----------------
    now = timezone.now()
    visit_qs = SiteVisit.objects.filter(project_id__in=project_ids)

    # upcoming (from now)
    upcoming_count = visit_qs.filter(
        status="SCHEDULED",
        scheduled_at__gte=now,
    ).count()
    result["site_visits"]["upcoming"] = upcoming_count

    # last_period
    visit_period_qs = apply_date_filter_dt(visit_qs, "scheduled_at", from_date, to_date)
    visit_rows = visit_period_qs.values("status").annotate(count=Count("id"))
    last_period_map = {}
    for row in visit_rows:
        key = row["status"] or "UNKNOWN"
        last_period_map[key] = row["count"]
    result["site_visits"]["last_period"] = last_period_map

    # ---------------- Cost sheets ----------------
    cs_qs = CostSheet.objects.filter(project_id__in=project_ids)
    cs_period_qs = apply_date_filter_date(cs_qs, "date", from_date, to_date)

    # count_by_status
    cs_status_rows = cs_period_qs.values("status").annotate(count=Count("id"))
    cs_status_map = {}
    for row in cs_status_rows:
        key = row["status"] or "UNKNOWN"
        cs_status_map[key] = row["count"]
    result["cost_sheets"]["count_by_status"] = cs_status_map

    # pipeline
    sent_total = (
        cs_period_qs.filter(status="SENT").aggregate(s=Sum("net_payable_amount"))["s"]
        or 0
    )
    accepted_total = (
        cs_period_qs.filter(status="ACCEPTED").aggregate(s=Sum("net_payable_amount"))[
            "s"
        ]
        or 0
    )
    result["cost_sheets"]["pipeline_value"] = {
        "sent_total": sent_total,
        "accepted_total": accepted_total,
    }

    # offers
    offers_qs = CostSheetAppliedOffer.objects.filter(
        costsheet__in=cs_period_qs
    ).select_related("costsheet")
    offers_total = offers_qs.aggregate(s=Sum("applied_amount"))["s"] or 0
    costsheets_with_offers = (
        offers_qs.values("costsheet_id").distinct().count()
    )

    result["cost_sheets"]["offers"] = {
        "total_discount": offers_total,
        "costsheets_with_offers": costsheets_with_offers,
    }

    # ---------------- Bookings ----------------
    booking_qs = Booking.objects.filter(project_id__in=project_ids)
    booking_period_qs = apply_date_filter_date(
        booking_qs, "booking_date", from_date, to_date
    )

    result["bookings"]["count"] = booking_period_qs.count()
    result["bookings"]["total_agreement_value"] = (
        booking_period_qs.aggregate(s=Sum("agreement_value"))["s"] or 0
    )

    booking_status_rows = booking_period_qs.values("status").annotate(
        count=Count("id")
    )
    booking_status_map = {}
    for row in booking_status_rows:
        key = row["status"] or "UNKNOWN"
        booking_status_map[key] = row["count"]
    result["bookings"]["by_status"] = booking_status_map

    # ---------------- KYC ----------------
    kyc_qs = BookingKycRequest.objects.filter(project_id__in=project_ids)
    kyc_period_qs = apply_date_filter_dt(
        kyc_qs, "created_at", from_date, to_date
    )

    kyc_rows = kyc_period_qs.values("status").annotate(count=Count("id"))
    kyc_status_map = {}
    for row in kyc_rows:
        key = row["status"] or "UNKNOWN"
        kyc_status_map[key] = row["count"]
    result["kyc"]["requests_by_status"] = kyc_status_map

    kyc_avg = kyc_period_qs.aggregate(a=Avg("amount"))["a"] or 0
    result["kyc"]["avg_amount"] = kyc_avg

    # ---------------- Channel partners ----------------

    # Leads per CP (group by cp.user_id)
    cp_lead_rows = (
        SalesLead.objects.filter(
            project_id__in=project_ids,
            channel_partner__isnull=False,
        )
        .values(
            "channel_partner__user_id",
            "channel_partner__user__first_name",
            "channel_partner__user__last_name",
        )
        .annotate(leads_count=Count("id"))
    )

    cp_stats = {}
    for row in cp_lead_rows:
        cp_user_id = row["channel_partner__user_id"]
        if not cp_user_id:
            continue
        full_name = (
            (row["channel_partner__user__first_name"] or "")
            + " "
            + (row["channel_partner__user__last_name"] or "")
        ).strip()
        cp_stats[cp_user_id] = {
            "cp_id": cp_user_id,
            "name": full_name or f"CP User {cp_user_id}",
            "leads_count": row["leads_count"],
            "bookings_count": 0,
            "booked_value": 0,
        }

    # Bookings per CP (group by booking.channel_partner user)
    cp_booking_rows = (
        booking_qs.filter(channel_partner__isnull=False)
        .values("channel_partner_id")
        .annotate(
            bookings_count=Count("id"),
            booked_value=Sum("agreement_value"),
        )
    )

    for row in cp_booking_rows:
        cp_user_id = row["channel_partner_id"]
        if cp_user_id not in cp_stats:
            cp_stats[cp_user_id] = {
                "cp_id": cp_user_id,
                "name": f"CP User {cp_user_id}",
                "leads_count": 0,
                "bookings_count": 0,
                "booked_value": 0,
            }
        cp_stats[cp_user_id]["bookings_count"] += row["bookings_count"] or 0
        cp_stats[cp_user_id]["booked_value"] += row["booked_value"] or 0

    cp_summary_list = list(cp_stats.values())
    result["channel_partners"]["cp_summary"] = cp_summary_list

    # top_cps_by_value: full objects (id + name + stats), not just IDs
    sorted_cp = sorted(
        cp_summary_list,
        key=lambda x: x.get("booked_value") or 0,
        reverse=True,
    )
    result["channel_partners"]["top_cps_by_value"] = sorted_cp[:5]

    return result

class BaseOwnedQuerysetMixin:
    """
    FINAL FIX:
    ADMIN and FULL_CONTROL see EXACTLY the same data.
    """

    def _get_role_code(self, user):
        role = getattr(user, "role", None)
        if not role:
            return None
        if isinstance(role, str):
            return role.upper()
        return getattr(role, "code", None)

    def _get_effective_admin(self, user):
        if not user or not user.is_authenticated:
            return None

        if user.is_staff:
            return None

        role_code = self._get_role_code(user)

        if role_code == "ADMIN":
            return user

        if role_code == "FULL_CONTROL":
            return getattr(user, "admin", None)

        return getattr(user, "admin", None)

    def filter_owned(self, qs, field="project__belongs_to_id"):
        user = self.request.user

        # staff sees everything
        if user.is_staff:
            return qs

        admin_user = self._get_effective_admin(user)

        if admin_user:
            return qs.filter(**{field: admin_user.id})

        return qs.none()


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        if not is_admin_like(user):
            return Response(
                {"success": False, "detail": "Only admin users can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            project_ids = get_filtered_project_ids(request, user)
            from_date, to_date = get_date_range(request)

            data = build_admin_dashboard(
                user, project_ids, from_date, to_date
            )
            return Response(
                {"success": True, "data": data},
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            logger.exception("Admin dashboard error")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_200_OK,
            )

# =====================================================
# Sales Dashboard
# =====================================================

def build_sales_dashboard(user, project_ids, from_date, to_date):
    """
    Dashboard for Sales / Reception / Calling Team user.
    Uses only leads / visits / sheets / bookings relevant to this user.
    """
    result = {
        "summary": {
            "my_active_leads": 0,
            "my_new_leads": 0,
        },
        "leads": {
            "by_stage": {},
            "by_classification": {},
        },
        "followups": {
            "today": 0,
            "overdue": 0,
            "next_7_days": 0,
        },
        "site_visits": {
            "upcoming": 0,
            "last_period": {},
        },
        "cost_sheets": {
            "count_by_status": {},
            "pipeline_value": {
                "sent_total": 0,
                "accepted_total": 0,
            },
        },
        "bookings": {
            "my_bookings_count": 0,
            "my_bookings_value": 0,
            "conversion_rate": 0,
        },
    }

    if not project_ids:
        return result

    # ---------------- Leads for this user ----------------
    lead_qs = SalesLead.objects.filter(
        project_id__in=project_ids,
        current_owner=user,
    )

    active_leads_qs = lead_qs  # optionally filter non-closed
    result["summary"]["my_active_leads"] = active_leads_qs.count()

    lead_period_qs = apply_date_filter_dt(
        lead_qs, "created_at", from_date, to_date
    )
    result["summary"]["my_new_leads"] = lead_period_qs.count()

    # by_stage: latest stage entries for these leads
    latest_stage_ids = (
        SalesLeadStageHistory.objects.filter(sales_lead__in=lead_qs)
        .values("sales_lead_id")
        .annotate(last_id=Max("id"))
        .values_list("last_id", flat=True)
    )
    stage_qs = SalesLeadStageHistory.objects.filter(id__in=list(latest_stage_ids))
    stage_rows = stage_qs.values("stage__name").annotate(count=Count("id"))
    by_stage = {}
    for row in stage_rows:
        key = row["stage__name"] or "Unknown"
        by_stage[key] = row["count"]
    result["leads"]["by_stage"] = by_stage

    # by_classification
    cls_rows = lead_qs.values("classification__name").annotate(count=Count("id"))
    by_classification = {}
    for row in cls_rows:
        key = row["classification__name"] or "Unclassified"
        by_classification[key] = row["count"]
    result["leads"]["by_classification"] = by_classification

    # ---------------- Follow-ups ----------------
    # SalesLeadUpdate created_by this user and type FOLLOW_UP/REMINDER
    fu_qs = SalesLeadUpdate.objects.filter(
        created_by=user,
        update_type__in=["FOLLOW_UP", "REMINDER"],
    )

    today = timezone.now().date()
    next_7 = today + timedelta(days=7)

    result["followups"]["today"] = fu_qs.filter(
        event_date__date=today
    ).count()
    result["followups"]["overdue"] = fu_qs.filter(
        event_date__date__lt=today
    ).count()
    result["followups"]["next_7_days"] = fu_qs.filter(
        event_date__date__gt=today,
        event_date__date__lte=next_7,
    ).count()

    # ---------------- Site visits ----------------
    visits_qs = SiteVisit.objects.filter(
        Q(lead__current_owner=user) | Q(created_by=user),
        project_id__in=project_ids,
    )

    now = timezone.now()
    upcoming_count = visits_qs.filter(
        status="SCHEDULED",
        scheduled_at__gte=now,
    ).count()
    result["site_visits"]["upcoming"] = upcoming_count

    visits_period_qs = apply_date_filter_dt(
        visits_qs, "scheduled_at", from_date, to_date
    )
    v_rows = visits_period_qs.values("status").annotate(count=Count("id"))
    last_period_map = {}
    for row in v_rows:
        key = row["status"] or "UNKNOWN"
        last_period_map[key] = row["count"]
    result["site_visits"]["last_period"] = last_period_map

    # ---------------- Cost sheets (prepared_by user) ----------------
    cs_qs = CostSheet.objects.filter(
        project_id__in=project_ids,
        prepared_by=user,
    )
    cs_period_qs = apply_date_filter_date(cs_qs, "date", from_date, to_date)

    cs_status_rows = cs_period_qs.values("status").annotate(count=Count("id"))
    cs_status_map = {}
    for row in cs_status_rows:
        key = row["status"] or "UNKNOWN"
        cs_status_map[key] = row["count"]
    result["cost_sheets"]["count_by_status"] = cs_status_map

    sent_total = (
        cs_period_qs.filter(status="SENT").aggregate(s=Sum("net_payable_amount"))["s"]
        or 0
    )
    accepted_total = (
        cs_period_qs.filter(status="ACCEPTED").aggregate(
            s=Sum("net_payable_amount")
        )["s"]
        or 0
    )
    result["cost_sheets"]["pipeline_value"] = {
        "sent_total": sent_total,
        "accepted_total": accepted_total,
    }

    # ---------------- Bookings for this user ----------------
    # decide whether to use created_by or lead.current_owner; here created_by
    booking_qs = Booking.objects.filter(
        project_id__in=project_ids,
        created_by=user,
    )
    booking_period_qs = apply_date_filter_date(
        booking_qs, "booking_date", from_date, to_date
    )

    my_bookings_count = booking_period_qs.count()
    my_bookings_value = (
        booking_period_qs.aggregate(s=Sum("agreement_value"))["s"] or 0
    )

    # Conversion rate = bookings / leads (avoid zero div)
    leads_count_for_period = lead_period_qs.count()
    if leads_count_for_period > 0:
        conversion_rate = (my_bookings_count / leads_count_for_period) * 100
    else:
        conversion_rate = 0

    result["bookings"] = {
        "my_bookings_count": my_bookings_count,
        "my_bookings_value": my_bookings_value,
        "conversion_rate": round(conversion_rate, 2),
    }

    return result
class SalesDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        try:
            project_ids = get_filtered_project_ids(request, user)
            from_date, to_date = get_date_range(request)

            # ✅ ADMIN / FULL_CONTROL → return ADMIN dashboard
            if is_admin_like(user):
                data = build_admin_dashboard(
                    user, project_ids, from_date, to_date
                )
                return Response(
                    {"success": True, "data": data},
                    status=status.HTTP_200_OK,
                )

            # ✅ SALES / RECEPTION → sales dashboard
            data = build_sales_dashboard(
                user, project_ids, from_date, to_date
            )
            return Response(
                {"success": True, "data": data},
                status=status.HTTP_200_OK,
            )

        except Exception as exc:
            logger.exception("Sales dashboard error")
            return Response(
                {"success": False, "error": str(exc)},
                status=status.HTTP_200_OK,
            )



# =====================================================
# Channel Partner Dashboard
# =====================================================

def build_cp_dashboard(user, project_ids, from_date, to_date):
    """
    Dashboard for Channel Partner user.
    Uses their CP profile + CP bookings.
    """
    result = {
        "summary": {
            "my_leads": 0,
            "my_new_leads": 0,
            "my_bookings": 0,
            "my_bookings_value": 0,
        },
        "leads": {
            "by_stage": {},
            "by_status": {},
        },
        "bookings": {
            "by_project": [],
        },
        "earnings": {
            "estimated_commission": 0,
            "currency": "INR",
        },
    }

    cp_profile = getattr(user, "channel_profile", None)
    if not cp_profile or not project_ids:
        return result

    # ---------------- Leads via this CP ----------------
    lead_qs = SalesLead.objects.filter(
        project_id__in=project_ids,
        channel_partner=cp_profile,
    )
    result["summary"]["my_leads"] = lead_qs.count()

    lead_period_qs = apply_date_filter_dt(
        lead_qs, "created_at", from_date, to_date
    )
    result["summary"]["my_new_leads"] = lead_period_qs.count()

    # by_stage (latest stage)
    latest_stage_ids = (
        SalesLeadStageHistory.objects.filter(sales_lead__in=lead_qs)
        .values("sales_lead_id")
        .annotate(last_id=Max("id"))
        .values_list("last_id", flat=True)
    )
    stage_qs = SalesLeadStageHistory.objects.filter(id__in=list(latest_stage_ids))
    stage_rows = stage_qs.values("stage__name").annotate(count=Count("id"))
    by_stage = {}
    for row in stage_rows:
        key = row["stage__name"] or "Unknown"
        by_stage[key] = row["count"]
    result["leads"]["by_stage"] = by_stage

    # by_status (LeadStatus)
    status_rows = lead_qs.values("status__name").annotate(count=Count("id"))
    by_status = {}
    for row in status_rows:
        key = row["status__name"] or "Unknown"
        by_status[key] = row["count"]
    result["leads"]["by_status"] = by_status

    # ---------------- Bookings via this CP ----------------
    booking_qs = Booking.objects.filter(
        project_id__in=project_ids,
        channel_partner=user,
    )
    booking_period_qs = apply_date_filter_date(
        booking_qs, "booking_date", from_date, to_date
    )

    my_bookings_count = booking_period_qs.count()
    my_bookings_value = (
        booking_period_qs.aggregate(s=Sum("agreement_value"))["s"] or 0
    )
    result["summary"]["my_bookings"] = my_bookings_count
    result["summary"]["my_bookings_value"] = my_bookings_value

    # by_project
    by_project_rows = (
        booking_period_qs.values("project_id", "project__name")
        .annotate(
            bookings_count=Count("id"),
            bookings_value=Sum("agreement_value"),
        )
        .order_by("project__name")
    )
    by_project_list = []
    for row in by_project_rows:
        by_project_list.append(
            {
                "project_id": row["project_id"],
                "project_name": row["project__name"],
                "bookings_count": row["bookings_count"],
                "bookings_value": row["bookings_value"] or 0,
            }
        )
    result["bookings"]["by_project"] = by_project_list

    # ---------------- Estimated commission ----------------
    estimated_commission = 0
    tier = cp_profile.partner_tier
    if tier:
        percent = tier.commission_percent
        flat_amount = tier.commission_amount

        if percent:
            estimated_commission += (my_bookings_value or 0) * (percent / 100)
        if flat_amount:
            estimated_commission += my_bookings_count * flat_amount

    result["earnings"]["estimated_commission"] = estimated_commission
    result["earnings"]["currency"] = "INR"

    return result


class ChannelPartnerDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            project_ids = get_filtered_project_ids(request, request.user)
            from_date, to_date = get_date_range(request)

            data = build_cp_dashboard(
                request.user, project_ids, from_date, to_date
            )
            return Response(
                {"success": True, "data": data},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("CP dashboard error")
            return Response(
                {
                    "success": False,
                    "error": str(exc),
                },
                status=status.HTTP_200_OK,
            )
