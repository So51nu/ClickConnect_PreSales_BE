# salelead/views_email_otp.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import random

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.response import Response

from django.utils import timezone
from datetime import timedelta
import random
import logging

from .models import LeadEmailOTP
from .tasks import send_lead_email_otp   # yahi @shared_task hai

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def start_lead_email_otp(request):
    """
    POST /api/sales/sales-leads/email-otp/start/
    { "email": "user@example.com" }
    """
    print("🔹 [start_lead_email_otp] Called")
    logger.info("🔹 [start_lead_email_otp] Called")

    email = (request.data.get("email") or "").strip()
    print(f"🔹 [start_lead_email_otp] Incoming email={email!r}")
    logger.info("🔹 [start_lead_email_otp] Incoming email=%s", email)

    if not email:
        print("⚠️ [start_lead_email_otp] Missing email")
        logger.warning("⚠️ [start_lead_email_otp] Missing email")
        return Response(
            {"email": "This field is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    deleted, _ = LeadEmailOTP.objects.filter(email=email).delete()
    print(f"🔹 [start_lead_email_otp] Old OTP deleted count={deleted}")
    logger.info("🔹 [start_lead_email_otp] Old OTP deleted count=%s", deleted)

    otp_code = f"{random.randint(0, 999999):06d}"
    print(f"🔹 [start_lead_email_otp] Generated OTP={otp_code}")
    logger.info("🔹 [start_lead_email_otp] Generated OTP=%s", otp_code)

    otp_obj = LeadEmailOTP.objects.create(
        email=email,
        otp_code=otp_code,
        expires_at=timezone.now() + timedelta(minutes=10),
    )
    print(f"✅ [start_lead_email_otp] OTP row created id={otp_obj.id}")
    logger.info("✅ [start_lead_email_otp] OTP row created id=%s", otp_obj.id)

    # 🔹 Asynchronous email via Celery
    try:
        print(f"🔹 [start_lead_email_otp] Queuing Celery task for id={otp_obj.id}")
        logger.info("🔹 [start_lead_email_otp] Queuing Celery task for id=%s", otp_obj.id)
        send_lead_email_otp.delay(otp_obj.id)
        print("✅ [start_lead_email_otp] Celery task queued")
        logger.info("✅ [start_lead_email_otp] Celery task queued")
    except Exception as e:
        print(f"❌ [start_lead_email_otp] Celery queuing FAILED: {e}")
        logger.exception("❌ [start_lead_email_otp] Celery queuing FAILED")
        return Response(
            {"detail": "Failed to queue OTP email task."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {"detail": "OTP sent to email."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_lead_email_otp(request):
    """
    POST /api/sales/sales-leads/email-otp/verify/
    { "email": "user@example.com", "otp": "123456" }
    """
    email = (request.data.get("email") or "").strip()
    otp = (request.data.get("otp") or "").strip()

    if not email or not otp:
        return Response(
            {"detail": "email and otp are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        otp_obj = (
            LeadEmailOTP.objects
            .filter(email=email)
            .latest("created_at")
        )
    except LeadEmailOTP.DoesNotExist:
        return Response(
            {"detail": "OTP not found, please request again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # expired?
    if otp_obj.expires_at < timezone.now():
        return Response(
            {"detail": "OTP expired. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # wrong code?
    if otp_obj.otp_code != otp:
        otp_obj.attempts += 1
        otp_obj.save(update_fields=["attempts"])
        return Response(
            {"detail": "Invalid OTP."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # success
    otp_obj.is_verified = True
    otp_obj.save(update_fields=["is_verified"])

    return Response(
        {"detail": "Email verified."},
        status=status.HTTP_200_OK,
    )
