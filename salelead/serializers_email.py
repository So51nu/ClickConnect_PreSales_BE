# salelead/serializers_email.py
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import SalesLead, SalesLeadEmailLog, EmailType, EmailStatus


class SalesLeadEmailLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for showing email logs."""

    sales_lead_id = serializers.IntegerField(source="sales_lead.id", read_only=True)
    sales_lead_name = serializers.SerializerMethodField()
    sales_lead_email = serializers.EmailField(source="sales_lead.email", read_only=True)

    sent_by = serializers.SerializerMethodField()

    class Meta:
        model = SalesLeadEmailLog
        fields = [
            "id",
            "sales_lead_id",
            "sales_lead_name",
            "sales_lead_email",
            "email_type",
            "subject",
            "body",
            "to_email",
            "cc",
            "bcc",
            "from_email",
            "sent_by",
            "status",
            "sent_at",
            "created_at",
        ]
        read_only_fields = fields  # saara read-only

    def get_sales_lead_name(self, obj):
        lead = obj.sales_lead
        if not lead:
            return ""
        name = (lead.first_name or "") + (" " + lead.last_name if lead.last_name else "")
        return name.strip() or lead.email or lead.mobile_number or f"#{lead.pk}"

    def get_sent_by(self, obj):
        u = obj.sent_by
        if not u:
            return None
        full_name = (u.get_full_name() or "").strip()
        return {
            "id": u.id,
            "username": u.username,
            "name": full_name or u.username,
            "email": u.email,
        }


class SalesLeadEmailSendSerializer(serializers.Serializer):
    """
    For sending an email & creating log.

    Request:
    {
      "sales_lead_id": 10,
      "subject": "Thank you for visiting",
      "body": "Dear Mr X ...",
      "email_type": "FOLLOWUP",  // optional
      "cc": ["x@y.com", "z@y.com"],   // optional
      "bcc": []
    }
    """

    sales_lead_id = serializers.IntegerField()
    subject = serializers.CharField(max_length=255)
    body = serializers.CharField()
    email_type = serializers.ChoiceField(
        choices=EmailType.choices, default=EmailType.OTHER, required=False
    )

    # cc/bcc as list of emails (frontend mein array bhejo)
    cc = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True,
    )
    bcc = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        lead_id = attrs.get("sales_lead_id")
        try:
            lead = SalesLead.objects.get(pk=lead_id)
        except SalesLead.DoesNotExist:
            raise serializers.ValidationError(
                {"sales_lead_id": "SalesLead not found."}
            )

        if not lead.email:
          # yahi requirement: mail lead se hi lena
            raise serializers.ValidationError(
                {"sales_lead_id": "This lead has no email address."}
            )

        attrs["_lead"] = lead
        return attrs

    def create(self, validated_data):
        """
        Actually send mail + create log row.
        """
        from django.core.mail import EmailMultiAlternatives

        request = self.context.get("request")
        user = getattr(request, "user", None)

        lead = validated_data["_lead"]
        subject = validated_data["subject"]
        body = validated_data["body"]
        email_type = validated_data.get("email_type") or EmailType.OTHER
        cc_list = validated_data.get("cc", [])
        bcc_list = validated_data.get("bcc", [])

        to_email = lead.email
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@example.com"

        # default status
        status_value = EmailStatus.QUEUED
        sent_at = None

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=from_email,
                to=[to_email],
                cc=cc_list or None,
                bcc=bcc_list or None,
            )
            sent_count = msg.send()
            if sent_count > 0:
                status_value = EmailStatus.SENT
                sent_at = timezone.now()
            else:
                status_value = EmailStatus.FAILED
        except Exception:
            status_value = EmailStatus.FAILED

        log = SalesLeadEmailLog.objects.create(
            sales_lead=lead,
            email_type=email_type,
            subject=subject,
            body=body,
            to_email=to_email,
            cc=",".join(cc_list) if cc_list else "",
            bcc=",".join(bcc_list) if bcc_list else "",
            from_email=from_email,
            sent_by=user if user and user.is_authenticated else None,
            status=status_value,
            sent_at=sent_at,
        )

        return log
