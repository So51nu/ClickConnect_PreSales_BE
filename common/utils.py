# notifications/utils.py
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from clientsetup.models import Notification, NotificationDispatchLog
from clientsetup.models import NotificationType, NotificationPriority, DeliveryMethod, ReadStatus, RowStatus  # adjust import
import uuid

def _generate_notification_code() -> str:
    return f"n_{uuid.uuid4().hex[:12]}"

def create_notification(
    *,
    user,
    message: str,
    project=None,
    notif_type=NotificationType.SYSTEM,
    priority=NotificationPriority.MEDIUM,
    delivery_method=DeliveryMethod.EMAIL,
    related_object=None,
    scheduled_at=None,
    expires_on=None,
):
    content_type = None
    object_id = None
    if related_object is not None:
        content_type = ContentType.objects.get_for_model(related_object.__class__)
        object_id = related_object.pk

    notif = Notification.objects.create(
        code=_generate_notification_code(),
        project=project,
        user=user,
        notif_type=notif_type,
        message=message,
        priority=priority,
        delivery_method=delivery_method,
        scheduled_at=scheduled_at,
        expires_on=expires_on,
        read_status=ReadStatus.UNREAD,
        status=RowStatus.ACTIVE,
        content_type=content_type,
        object_id=object_id,
    )
    return notif

def send_email_and_log(notification: Notification, subject: str, to_email: str):
    """
    Helper: email + NotificationDispatchLog.
    """
    if not to_email:
        return

    success = False
    response_meta = {}

    try:
        send_mail(
            subject,
            notification.message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            fail_silently=False,
        )
        success = True
    except Exception as exc:
        response_meta = {"error": str(exc)}

    NotificationDispatchLog.objects.create(
        notification=notification,
        attempt_no=1,
        channel=DeliveryMethod.EMAIL,
        success=success,
        response_meta=response_meta,
    )

    if success and notification.scheduled_at and notification.scheduled_at > timezone.now():
        pass

    return success




import re

def get_project_code(project) -> str:
    """
    Project name se 2-letter code banao, clean karke.
    e.g. 'Deep Shikhar' -> 'DS'
    Fallback: PR + project.id
    """
    if not project:
        return "PR"

    name = (getattr(project, "name", None) or "").strip()
    if not name:
        return f"PR{project.id}"

    # sirf letters+digits lo
    cleaned = re.sub(r"[^A-Za-z0-9]", "", name.upper())
    if len(cleaned) >= 2:
        return cleaned[:2]
    if cleaned:
        return cleaned + str(project.id or "")
    return f"PR{project.id}"




