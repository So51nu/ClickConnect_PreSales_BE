# common/tasks.py

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail
from decimal import Decimal
from datetime import datetime, timedelta

from common.utils import create_notification, send_email_and_log

from salelead.models import (
    SalesLead,
    SalesLeadUpdate,
    SiteVisit,
    SiteVisitRescheduleHistory,
)
from costsheet.models import CostSheet
from booking.models import Booking
from clientsetup.models import (
    Project,
    Inventory,
    InventoryStatusHistory,
    AvailabilityStatus,
    UnitStatus,
)

# Window for “now ± window” matching in reminder tasks
REMINDER_WINDOW_MINUTES = 5


# 🔹 Helper: project ka safe title nikaalne ke liye
def _project_title(project):
    if not project:
        return "Project"

    return (
        getattr(project, "name", None)
        or getattr(project, "project_name", None)
        or getattr(project, "project_id", None)
        or f"Project #{project.pk}"
    )


# ---------- 1) SalesLeadUpdate emails (existing) ----------

@shared_task
def send_salesleadupdate_email(update_id: int):
    try:
        upd = SalesLeadUpdate.objects.select_related(
            "created_by",
            "sales_lead",
        ).get(pk=update_id)
    except SalesLeadUpdate.DoesNotExist:
        return

    user = upd.created_by
    if not user or not user.email:
        return

    lead = upd.sales_lead
    subject = f"[Lead #{lead.id}] {upd.title}"

    msg = (
        f"Lead Update Type: {upd.update_type}\n"
        f"Lead ID: {lead.id}\n"
        f"Title: {upd.title}\n"
        f"Info: {upd.info}\n"
        f"Event Date: {upd.event_date}\n"
    )

    notif = create_notification(
        user=user,
        project=getattr(lead, "project", None),
        message=msg,
        related_object=upd,
    )

    ok = send_email_and_log(notif, subject, user.email)

    if ok:
        SalesLeadUpdate.objects.filter(pk=upd.pk).update(
            reminder_sent_at=timezone.now()
        )


@shared_task
def ping_debug():
    print("Celery OK for estate project")


# ---------- 2) SiteVisit created / rescheduled emails (existing) ----------

@shared_task
def send_sitevisit_created_email(sitevisit_id: int):
    try:
        sv = SiteVisit.objects.select_related(
            "created_by",
            "lead",
            "project",
        ).get(pk=sitevisit_id)
    except SiteVisit.DoesNotExist:
        return

    lead = sv.lead
    project = sv.project
    project_title = _project_title(project)
    recipients = []

    if sv.created_by and sv.created_by.email:
        recipients.append(("Site Visit Created (You)", sv.created_by, sv.created_by.email))

    if getattr(lead, "email", None):
        recipients.append(("Site Visit Scheduled", lead, lead.email))

    for label, user_or_lead, email in recipients:
        subject = f"[{project_title}] Site Visit Scheduled"
        msg = (
            f"{label}\n\n"
            f"Project: {project_title}\n"
            f"Lead ID: {lead.id}\n"
            f"Name: {getattr(lead, 'full_name', '')}\n"
            f"Unit: {sv.inventory or sv.unit_config or ''}\n"
            f"Scheduled At: {sv.scheduled_at}\n"
            f"Status: {sv.status}\n"
        )

        user_for_notif = sv.created_by or getattr(lead, "current_owner", None)

        if user_for_notif and email:
            notif = create_notification(
                user=user_for_notif,
                project=project,
                message=msg,
                related_object=sv,
            )
            send_email_and_log(notif, subject, email)

    SiteVisit.objects.filter(pk=sv.pk).update(reminder_sent_at=timezone.now())


@shared_task
def send_sitevisit_reschedule_email(reschedule_id: int):
    try:
        rh = SiteVisitRescheduleHistory.objects.select_related(
            "site_visit",
            "created_by",
            "site_visit__lead",
            "site_visit__project",
        ).get(pk=reschedule_id)
    except SiteVisitRescheduleHistory.DoesNotExist:
        return

    sv = rh.site_visit
    lead = sv.lead
    project = sv.project
    project_title = _project_title(project)
    recipients = []

    if rh.created_by and rh.created_by.email:
        recipients.append(("Site Visit Rescheduled (You)", rh.created_by, rh.created_by.email))

    if getattr(lead, "email", None):
        recipients.append(("Site Visit Rescheduled", lead, lead.email))

    for label, user_or_lead, email in recipients:
        subject = f"[{project_title}] Site Visit Rescheduled"
        msg = (
            f"{label}\n\n"
            f"Project: {project_title}\n"
            f"Lead ID: {lead.id}\n"
            f"Old Time: {rh.old_scheduled_at}\n"
            f"New Time: {rh.new_scheduled_at}\n"
            f"Reason: {rh.reason}\n"
        )

        user_for_notif = (
            rh.created_by
            or sv.created_by
            or getattr(lead, "current_owner", None)
        )

        if user_for_notif and email:
            notif = create_notification(
                user=user_for_notif,
                project=project,
                message=msg,
                related_object=sv,
            )
            send_email_and_log(notif, subject, email)


# ---------- 3) New lead to CP (existing) ----------

@shared_task
def send_new_lead_to_cp(lead_id: int):
    try:
        lead = SalesLead.objects.select_related(
            "channel_partner",
            "created_by",
            "project",
        ).get(pk=lead_id)
    except SalesLead.DoesNotExist:
        return

    cp_profile = getattr(lead, "channel_partner", None)
    cp_email = None
    cp_user = None

    if cp_profile:
        cp_email = (
            getattr(cp_profile, "email", None)
            or getattr(getattr(cp_profile, "user", None), "email", None)
        )
        cp_user = getattr(cp_profile, "user", None)

    if not cp_email:
        return

    project_title = _project_title(lead.project)

    subject = f"[New Lead] Project: {project_title}"
    msg = (
        f"A new lead has been assigned to you.\n\n"
        f"Lead ID: {lead.id}\n"
        f"Name: {lead.full_name if hasattr(lead, 'full_name') else lead.first_name}\n"
        f"Mobile: {getattr(lead, 'mobile_number', '')}\n"
        f"Project: {project_title}\n"
        f"Source: {getattr(lead, 'source', None)}\n"
    )

    notif = create_notification(
        user=cp_user or lead.created_by,
        project=lead.project,
        message=msg,
        related_object=lead,
    )
    send_email_and_log(notif, subject, cp_email)


# ---------- 4) CostSheet email (existing) ----------

@shared_task
def send_costsheet_email(costsheet_id: int):
    try:
        cs = (
            CostSheet.objects
            .select_related(
                "lead",
                "lead__channel_partner",
                "lead__created_by",
                "project",
                "prepared_by",
            )
            .get(pk=costsheet_id)
        )
    except CostSheet.DoesNotExist:
        return

    lead = cs.lead
    project = cs.project
    project_title = _project_title(project)

    recipients = []

    if getattr(lead, "email", None):
        recipients.append(("Quotation generated for you", lead, lead.email))

    if lead.created_by and lead.created_by.email:
        recipients.append(("Quotation for your lead", lead.created_by, lead.created_by.email))

    cp_profile = getattr(lead, "channel_partner", None)
    cp_email = None
    cp_user = None
    if cp_profile:
        cp_email = (
            getattr(cp_profile, "email", None)
            or getattr(getattr(cp_profile, "user", None), "email", None)
        )
        cp_user = getattr(cp_profile, "user", None)
    if cp_email:
        recipients.append(("Quotation for your channel lead", cp_user, cp_email))

    for label, user_or_cp, email in recipients:
        subject = f"[Quotation #{cs.quotation_no}] {project_title}"
        msg = (
            f"{label}\n\n"
            f"Project: {project_title}\n"
            f"Customer: {cs.customer_name}\n"
            f"Unit: {cs.unit_no}\n"
            f"Base Value: {cs.base_value}\n"
            f"Net Payable: {cs.net_payable_amount}\n"
            f"Valid till: {cs.valid_till}\n"
        )

        user_for_notif = user_or_cp or cs.prepared_by or lead.created_by

        if user_for_notif and email:
            notif = create_notification(
                user=user_for_notif,
                project=project,
                message=msg,
                related_object=cs,
            )
            send_email_and_log(notif, subject, email)


# ---------- 5) Booking created + slab reminders (existing) ----------

@shared_task
def send_booking_created_email(booking_id: int):
    try:
        bk = (
            Booking.objects
            .select_related("sales_lead", "project", "channel_partner", "created_by")
            .get(pk=booking_id)
        )
    except Booking.DoesNotExist:
        return

    lead = bk.sales_lead
    project = bk.project
    project_title = _project_title(project)

    recipients = []

    if lead and getattr(lead, "email", None):
        recipients.append(("Booking created from your lead", lead, lead.email))

    if bk.primary_email:
        recipients.append(("Your flat booking details", None, bk.primary_email))

    cp_user = bk.channel_partner
    if cp_user and cp_user.email:
        recipients.append(("Booking created for your lead", cp_user, cp_user.email))

    for label, user_or_lead, email in recipients:
        subject = f"[Booking {bk.form_ref_no}] {project_title}"
        msg = (
            f"{label}\n\n"
            f"Project: {project_title}\n"
            f"Unit: {bk.unit}\n"
            f"Agreement Value: {bk.agreement_value}\n"
            f"Booking Date: {bk.booking_date}\n"
            f"Status: {bk.status}\n"
        )

        user_for_notif = user_or_lead or bk.created_by or cp_user

        if user_for_notif and email:
            notif = create_notification(
                user=user_for_notif,
                project=project,
                message=msg,
                related_object=bk,
            )
            send_email_and_log(notif, subject, email)


@shared_task
def send_booking_slab_reminder(booking_id: int, slab_index: int):
    try:
        bk = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return

    plan = bk.custom_payment_plan or {}
    slabs = plan.get("slabs") or []
    if not (0 <= slab_index < len(slabs)):
        return

    slab = slabs[slab_index]
    slab_name = slab.get("name", f"Slab {slab_index + 1}")
    slab_pct = slab.get("percentage", 0)
    slab_due_days = slab.get("days", 0)

    due_date = bk.booking_date + timedelta(days=int(slab_due_days))
    project_title = _project_title(bk.project)

    subject = f"[Payment Reminder] {slab_name} – Booking {bk.form_ref_no}"
    msg = (
        f"This is a reminder for your payment slab.\n\n"
        f"Booking: {bk.form_ref_no}\n"
        f"Project: {project_title}\n"
        f"Due Slab: {slab_name}\n"
        f"Percentage: {slab_pct}% of agreement value ({bk.agreement_value})\n"
        f"Due Date: {due_date}\n"
    )

    to_email = None
    user_for_notif = None

    if bk.sales_lead and getattr(bk.sales_lead, "email", None):
        to_email = bk.sales_lead.email
        user_for_notif = getattr(bk.sales_lead, "current_owner", None) or bk.created_by
    elif bk.primary_email:
        to_email = bk.primary_email
        user_for_notif = bk.created_by

    if not (to_email and user_for_notif):
        return

    notif = create_notification(
        user=user_for_notif,
        project=bk.project,
        message=msg,
        related_object=bk,
        scheduled_at=timezone.now(),
    )
    send_email_and_log(notif, subject, to_email)


@shared_task
def schedule_booking_slab_reminders(booking_id: int, reminder_offset_days: int = 2):
    try:
        bk = Booking.objects.get(pk=booking_id)
    except Booking.DoesNotExist:
        return

    if bk.payment_plan_type != "CUSTOM" or not bk.custom_payment_plan:
        return

    slabs = bk.custom_payment_plan.get("slabs") or []
    if not slabs:
        return

    for idx, slab in enumerate(slabs):
        slab_days = int(slab.get("days", 0))
        due_date = bk.booking_date + timedelta(days=slab_days)
        reminder_date = due_date - timedelta(days=reminder_offset_days)

        eta = timezone.make_aware(
            datetime.combine(reminder_date, datetime.min.time()),
            timezone=timezone.get_current_timezone(),
        )

        if eta > timezone.now():
            send_booking_slab_reminder.apply_async(
                args=[booking_id, idx],
                eta=eta,
            )


# ---------- 6) NEW: helpers for dynamic reminders ----------

def _mark_reminder_sent(obj, offset_minutes: int):
    """
    obj.reminder_log ko update karega:
      key = str(offset_minutes)
      value = now.isoformat()
    """
    now = timezone.now()
    log = getattr(obj, "reminder_log", None) or {}
    key = str(offset_minutes)
    log[key] = now.isoformat()
    obj.reminder_log = log
    obj.save(update_fields=["reminder_log"])


def _was_reminder_sent(obj, offset_minutes: int) -> bool:
    log = getattr(obj, "reminder_log", None) or {}
    return str(offset_minutes) in log


# ---------- 7) NEW: Case 1 – auto unlock inventory blocks ----------

from celery import shared_task
from datetime import timedelta
from django.utils import timezone

from clientsetup.models import Inventory
from clientsetup.models import AvailabilityStatus, UnitStatus  # adjust import path
from clientsetup.models import InventoryStatusHistory          # exact path as per your app


@shared_task
def auto_unlock_expired_inventory_blocks():
    """
    Auto-unblock inventories jinka block period khatam ho chuka hai.

    Logic:
    - Inventory.availability_status = BLOCKED
    - blocked_until is not null
    - blocked_until <= now

    Action:
    - availability_status -> AVAILABLE
    - unit_status BLOCKED ho to -> AVAILABLE
    - blocked_until = None
    - InventoryStatusHistory row: reason = "Auto unblocked: block period expired"
    """
    now = timezone.now()

    # Sirf woh inventories jinke paas proper blocked_until hai aur BLOCKED hain
    blocked_qs = Inventory.objects.filter(
        availability_status=AvailabilityStatus.BLOCKED,
        blocked_until__isnull=False,
        blocked_until__lte=now,
    )

    for inv in blocked_qs:
        old_avail = inv.availability_status
        # UnitStatus ho sakta hai na ho enum – tumhare code ke hisaab se hai:
        old_unit_status = getattr(inv, "unit_status", None)

        # Unblock availability
        inv.availability_status = AvailabilityStatus.AVAILABLE

        # Agar unit_status bhi BLOCKED hai to usko bhi AVAILABLE karo
        if hasattr(inv, "unit_status") and inv.unit_status == UnitStatus.BLOCKED:
            inv.unit_status = UnitStatus.AVAILABLE

        # Block khatam ho chuka hai
        inv.blocked_until = None

        # Efficient save
        update_fields = ["availability_status", "blocked_until"]
        if hasattr(inv, "unit_status"):
            update_fields.append("unit_status")

        inv.save(update_fields=update_fields)

        # History log – IMPORTANT: tumhare model ke field names ye hain:
        # old_availability, new_availability
        InventoryStatusHistory.objects.create(
            inventory=inv,
            old_availability=old_avail,
            new_availability=inv.availability_status,
            reason="Auto unblocked: block period expired",
            changed_by=None,
        )


# ---------- 8) NEW: Case 2 – dynamic reminders for SalesLeadUpdate ----------

@shared_task
def send_due_salesleadupdate_reminders():
    """
    For each Project:
      - project.get_reminder_offsets() -> [1440, 60, 30, ...]
      - For each offset:
          event_date ke around (now + offset ± window) wale updates
          jinke liye us offset ka reminder_log entry nahi hai
          unko email + notification bhejo.
    """
    now = timezone.now()
    window = timedelta(minutes=REMINDER_WINDOW_MINUTES)

    projects = Project.objects.all()

    for project in projects:
        offsets = project.get_reminder_offsets()
        if not offsets:
            continue

        project_title = _project_title(project)

        for offset in offsets:
            target = now + timedelta(minutes=offset)
            start = target - window
            end = target + window

            updates = (
                SalesLeadUpdate.objects
                .select_related("sales_lead", "sales_lead__project", "created_by")
                .filter(
                    sales_lead__project=project,
                    event_date__gte=start,
                    event_date__lte=end,
                )
            )

            for upd in updates:
                if _was_reminder_sent(upd, offset):
                    continue

                lead = upd.sales_lead
                user = upd.created_by

                if not (user and user.email):
                    _mark_reminder_sent(upd, offset)
                    continue

                subject = f"[Reminder {offset} min] Lead #{lead.id} – {upd.title}"
                msg = (
                    f"This is a reminder for your scheduled lead activity.\n\n"
                    f"Project: {project_title}\n"
                    f"Lead ID: {lead.id}\n"
                    f"Title: {upd.title}\n"
                    f"Type: {upd.update_type}\n"
                    f"Event Time: {upd.event_date}\n"
                    f"Offset: {offset} minutes before event\n"
                )

                notif = create_notification(
                    user=user,
                    project=project,
                    message=msg,
                    related_object=upd,
                )
                send_email_and_log(notif, subject, user.email)

                _mark_reminder_sent(upd, offset)


# ---------- 9) NEW: Case 2 – dynamic reminders for SiteVisit ----------

@shared_task
def send_due_sitevisit_reminders():
    """
    Same Project.reminder_offsets_minutes config use karega,
    but SiteVisit.scheduled_at ke against.
    """
    now = timezone.now()
    window = timedelta(minutes=REMINDER_WINDOW_MINUTES)

    projects = Project.objects.all()

    for project in projects:
        offsets = project.get_reminder_offsets()
        if not offsets:
            continue

        project_title = _project_title(project)

        for offset in offsets:
            target = now + timedelta(minutes=offset)
            start = target - window
            end = target + window

            visits = (
                SiteVisit.objects
                .select_related("lead", "project", "created_by")
                .filter(
                    project=project,
                    scheduled_at__gte=start,
                    scheduled_at__lte=end,
                )
            )

            for sv in visits:
                if _was_reminder_sent(sv, offset):
                    continue

                lead = sv.lead

                recipients = []

                if getattr(lead, "email", None):
                    recipients.append(("Site Visit Reminder", lead, lead.email))

                if sv.created_by and sv.created_by.email:
                    recipients.append(("Your Site Visit Reminder", sv.created_by, sv.created_by.email))

                for label, user_or_lead, email in recipients:
                    subject = f"[Reminder {offset} min] Site Visit – {project_title}"
                    msg = (
                        f"{label}\n\n"
                        f"Project: {project_title}\n"
                        f"Lead ID: {lead.id}\n"
                        f"Name: {getattr(lead, 'full_name', getattr(lead, 'first_name', ''))}\n"
                        f"Unit: {sv.inventory or sv.unit_config or ''}\n"
                        f"Scheduled At: {sv.scheduled_at}\n"
                        f"Offset: {offset} minutes before visit\n"
                    )

                    user_for_notif = (
                        sv.created_by
                        or getattr(lead, "current_owner", None)
                    )

                    if user_for_notif and email:
                        notif = create_notification(
                            user=user_for_notif,
                            project=project,
                            message=msg,
                            related_object=sv,
                        )
                        send_email_and_log(notif, subject, email)

                _mark_reminder_sent(sv, offset)

