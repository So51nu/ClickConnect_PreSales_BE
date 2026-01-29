# salelead/tasks.py
import logging

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.exceptions import ValidationError

from .models import LeadSourceSystem, LeadEmailOTP
from .normalizers import normalize_google_sheet
from .views_integration import _create_or_update_from_normalized
from .tasks_integration import sync_google_sheet_opportunities


logger = logging.getLogger(__name__)


def fetch_rows_from_sheet():
    """
    Yaha actual Google Sheet API ka code aayega.
    Abhi demo ke liye dummy data.
    Har row ek dict ho.
    """
    return [
        {
            "RowId": "sheet-1",
            "Name": "Sheet User 1",
            "Email": "sheet1@example.com",
            "Phone": "9999999999",
            "SheetName": "Lead Sheet 1",
        },
        # aur rows...
    ]


@shared_task
def sync_google_sheet():
    """
    Periodic task: Google Sheet se rows read karo
    aur LeadOpportunity me store/update karo.
    Yaha ValidationError ko catch kar rahe hain taaki
    project_id null hone pe bhi Celery crash na kare.
    """
    rows = fetch_rows_from_sheet()
    created_count = 0
    updated_count = 0

    for row in rows:
        normalized = normalize_google_sheet(row)

        try:
            opp, created = _create_or_update_from_normalized(
                LeadSourceSystem.GOOGLE_SHEET,
                normalized,
                row,  # raw payload
            )
        except ValidationError as exc:
            logger.error(
                "Error syncing google sheet row %r: %s",
                row,
                getattr(exc, "detail", exc),
            )
            continue

        if created:
            created_count += 1
        else:
            updated_count += 1

    logger.info(
        "sync_google_sheet done: created=%s updated=%s total_rows=%s",
        created_count,
        updated_count,
        len(rows),
    )


from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

from .models import LeadEmailOTP   # path adjust

logger = logging.getLogger(__name__)


@shared_task
def send_lead_email_otp(otp_id: int):
    """
    Asynchronously send OTP email for lead verification.
    """
    print(f"🔸 [send_lead_email_otp] Task START otp_id={otp_id}")
    logger.info("🔸 [send_lead_email_otp] Task START otp_id=%s", otp_id)

    try:
        otp_obj = LeadEmailOTP.objects.get(pk=otp_id)
    except LeadEmailOTP.DoesNotExist:
        print(f"⚠️ [send_lead_email_otp] LeadEmailOTP {otp_id} not found")
        logger.warning("⚠️ [send_lead_email_otp] LeadEmailOTP %s not found", otp_id)
        return

    print(
        f"🔸 [send_lead_email_otp] Found OTP: email={otp_obj.email}, code={otp_obj.otp_code}, "
        f"expires_at={otp_obj.expires_at}"
    )
    logger.info(
        "🔸 [send_lead_email_otp] Found OTP: email=%s code=%s expires_at=%s",
        otp_obj.email,
        otp_obj.otp_code,
        otp_obj.expires_at,
    )

    subject = "Your email verification code"
    message = (
        f"Your verification code is: {otp_obj.otp_code}\n\n"
        "This code is valid for 10 minutes."
    )

    print(
        f"🔸 [send_lead_email_otp] Sending email via Django send_mail "
        f"from={settings.DEFAULT_FROM_EMAIL} to={otp_obj.email}"
    )
    logger.info(
        "🔸 [send_lead_email_otp] Sending email via Django send_mail from=%s to=%s",
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        otp_obj.email,
    )

    try:
        sent_count = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [otp_obj.email],
            fail_silently=False,  # keep False in debug
        )
        print(f"✅ [send_lead_email_otp] send_mail returned={sent_count}")
        logger.info("✅ [send_lead_email_otp] send_mail returned=%s", sent_count)
    except Exception as e:
        print(f"❌ [send_lead_email_otp] send_mail FAILED: {e}")
        logger.exception("❌ [send_lead_email_otp] send_mail FAILED")
        # Optionally mark OTP as failed, etc.
        return

    print(f"✅ [send_lead_email_otp] OTP email sent to {otp_obj.email}")
    logger.info("✅ [send_lead_email_otp] OTP email sent to %s", otp_obj.email)

