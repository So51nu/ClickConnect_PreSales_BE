# salelead/views_email.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import SalesLeadEmailLog
from .serializers_email import (
    SalesLeadEmailLogSerializer,
    SalesLeadEmailSendSerializer,
)


class SalesLeadEmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Email history + send endpoint.

    GET /api/sales/email-logs/?sales_lead_id=10
      -> list of logs for that lead

    POST /api/sales/email-logs/send/
      -> send email to lead.email using DEFAULT_FROM_EMAIL
         and create log row.
    """

    permission_classes = [IsAuthenticated]
    queryset = (
        SalesLeadEmailLog.objects
        .select_related("sales_lead", "sent_by")
        .order_by("-created_at")
    )

    def get_queryset(self):
        qs = super().get_queryset()
        lead_id = self.request.query_params.get("sales_lead_id") or \
                  self.request.query_params.get("lead_id")
        project_id = self.request.query_params.get("project_id")

        if lead_id:
            qs = qs.filter(sales_lead_id=lead_id)
        if project_id:
            qs = qs.filter(sales_lead__project_id=project_id)
        return qs

    def get_serializer_class(self):
        if self.action == "send":
            return SalesLeadEmailSendSerializer
        return SalesLeadEmailLogSerializer

    @action(detail=False, methods=["post"], url_path="send")
    def send(self, request, *args, **kwargs):
        """
        POST /api/sales/email-logs/send/

        Body:
        {
          "sales_lead_id": 10,
          "subject": "Hello",
          "body": "Body...",
          "email_type": "FOLLOWUP",
          "cc": ["x@y.com"],
          "bcc": []
        }
        """
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        log = serializer.save()  # SalesLeadEmailLog instance

        out = SalesLeadEmailLogSerializer(log, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)
