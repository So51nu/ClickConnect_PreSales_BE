# salelead/utils.py

import datetime

from django.utils import timezone

from salelead.models import (
    SiteVisit,              # ✅ agar alag app me hai to import path adjust kar lena
    SalesLeadEmailLog,
    LeadComment,
    SalesLeadUpdate,
    EmailStatus,
)


def _safe_ts(ts):
    """
    None / invalid ts ke liye bahut purana time de do
    taaki max(...) safely kaam kare.
    """
    if ts is None:
        return datetime.datetime(1900, 1, 1, tzinfo=timezone.utc)
    return ts


def get_latest_lead_remark(lead):
    """
    Lead ka sabse latest remark nikalo from:
      1) SiteVisit (outcome_notes / public_notes / internal_notes / reasons)
      2) StageHistory.notes
      3) SalesLeadUpdate:
            - info (DB field)
            - agar info empty ho to status_history.comment
            - agar wo bhi empty ho to title
      4) LeadComment.text
      5) SalesLeadEmailLog (subject / body)
    Jo bhi sabse latest timestamp wala hai, uska text return karenge.
    """

    candidates = []

    # ---------------- 1) SiteVisit notes ----------------
    latest_visit = (
        SiteVisit.objects
        .filter(lead_id=lead.id)
        .order_by("-scheduled_at", "-created_at")
        .first()
    )
    if latest_visit:
        visit_text = (
            (latest_visit.outcome_notes or "").strip()
            or (latest_visit.public_notes or "").strip()
            or (latest_visit.internal_notes or "").strip()
            or (latest_visit.cancelled_reason or "").strip()
            or (latest_visit.no_show_reason or "").strip()
        )
        if visit_text:
            candidates.append(
                {
                    "ts": latest_visit.scheduled_at or latest_visit.created_at,
                    "text": visit_text,
                    "source": "site_visit",
                }
            )

    # ---------------- 2) Stage history (notes) ----------------
    stage_qs = getattr(lead, "stage_history", None)
    if stage_qs is not None:
        latest_stage = (
            lead.stage_history
            .order_by("-event_date", "-created_at")
            .first()
        )
        if latest_stage:
            notes = (latest_stage.notes or "").strip()
            if notes:
                candidates.append(
                    {
                        "ts": latest_stage.event_date or latest_stage.created_at,
                        "text": notes,
                        "source": "stage_history",
                    }
                )

    # ---------------- 3) SalesLeadUpdate (follow-up / reminder / note) ----------------
    update_qs = getattr(lead, "updates", None)
    if update_qs is not None:
        latest_update = (
            lead.updates
            .order_by("-event_date", "-created_at")
            .first()
        )
        if latest_update:
            # ✅ DB field ka naam `info` hai, `remarks` nahi
            text = (latest_update.info or "").strip()

            # agar info blank hai to latest status_history.comment try karo
            if not text and hasattr(latest_update, "status_history"):
                hist = (
                    latest_update.status_history
                    .order_by("-event_date", "-created_at")
                    .first()
                )
                if hist and getattr(hist, "comment", ""):
                    text = hist.comment.strip()

            # agar abhi bhi kuch nahi mila to title use karo
            if not text:
                text = (latest_update.title or "").strip()

            if text:
                candidates.append(
                    {
                        "ts": latest_update.event_date or latest_update.created_at,
                        "text": text,
                        "source": "update",
                    }
                )

    # ---------------- 4) LeadComment ----------------
    comments_qs = getattr(lead, "comments", None)
    if comments_qs is not None:
        latest_comment = lead.comments.order_by("-created_at").first()
        if latest_comment and latest_comment.text:
            candidates.append(
                {
                    "ts": latest_comment.created_at,
                    "text": latest_comment.text.strip(),
                    "source": "comment",
                }
            )

    # ---------------- 5) Email logs ----------------
    # ---------------- 5) Email logs ----------------
    email_qs = getattr(lead, "email_logs", None)
    if email_qs is not None:
        # Tumhare case me sirf SENT emails hi meaningful hain
        latest_email = (
            lead.email_logs
            .filter(status=EmailStatus.SENT)
            .order_by("-sent_at", "-created_at")
            .first()
        )
        if latest_email:
            email_text = (
                (latest_email.subject or "").strip()
                or (latest_email.body or "").strip()
            )
            if email_text:
                candidates.append(
                    {
                        "ts": latest_email.sent_at or latest_email.created_at,
                        "text": email_text,
                        "source": "email",
                    }
                )


    # ---------------- FINAL: pick max by timestamp ----------------
    if not candidates:
        return None

    latest = max(candidates, key=lambda c: _safe_ts(c["ts"]))
    return latest["text"]



from clientsetup.models import Project
from accounts.models import ProjectUserAccess
from accounts.models import Role  # agar Role enum hai to

def _project_ids_for_user(user):
    """
    Return list of project IDs the user is allowed to access.
    - SUPERADMIN → sab projects
    - ADMIN (client) → apne belongs_to wale projects
    - Others → sirf jinke liye ProjectUserAccess row bana hai
    """

    if not user.is_authenticated:
        return []

    # 1) Superuser: sab kuch
    if user.is_superuser:
        return list(Project.objects.values_list("id", flat=True))

    # 2) Client Admin: apne hi projects (belongs_to = user)
    if getattr(user, "role", None) == Role.ADMIN:
        return list(
            Project.objects.filter(belongs_to=user, is_active=True)
            .values_list("id", flat=True)
        )

    # 3) Baaki sab: explicit per-user access
    qs = (
        ProjectUserAccess.objects
        .filter(user=user,is_active=True)
        .values_list("project_id", flat=True)
    )
    project_ids = list(qs)

    # Agar kisko access hi nahi diya → kuch bhi project nahi
    return project_ids


