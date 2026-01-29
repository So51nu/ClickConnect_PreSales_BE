from django.conf import settings
from django.core.mail import send_mail


def send_kyc_request_email(kyc_obj):
    """
    Sends mail to approver with one-time link.
    """
    token = kyc_obj.generate_one_time_token()

    frontend_base = getattr(
        settings,
        "FRONTEND_BASE_URL",
        "http://localhost:5173",
    )

    review_url = f"{frontend_base}/booking/kyc-review?token={token}"

    subject = f"[KYC] New Booking KYC Request #{kyc_obj.id}"
    snapshot = kyc_obj.snapshot or {}
    project_name = snapshot.get("project_name", "")
    unit_no = snapshot.get("unit_no", "")

    message = (
        f"Dear Approver,\n\n"
        f"A new booking KYC request has been created.\n\n"
        f"Project: {project_name}\n"
        f"Unit: {unit_no}\n"
        f"Proposed Amount: {kyc_obj.amount}\n"
        f"Current Status: {kyc_obj.status}\n\n"
        f"Click the link below to view full details and take a decision.\n"
        f"This link can be used only once:\n\n"
        f"{review_url}\n\n"
        f"Regards,\n"
        f"Pre-Sale Booking System"
    )

    # 🔴 FOR NOW: always send to your own Gmail so you can test
    approver_email = "vasisayed09421@gmail.com"

    # Later you can switch back to project.primary_admin once that's set properly:
    # approver_email = getattr(getattr(kyc_obj.project, "primary_admin", None), "email", None)
    # if not approver_email:
    #     approver_email = settings.EMAIL_HOST_USER

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,   # from = your Gmail
        [approver_email],
        fail_silently=False,        # 👈 IMPORTANT for debugging
    )
