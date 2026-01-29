# salelead/views_integrations.py
from django.conf import settings
from django.utils.crypto import constant_time_compare
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from salelead.models import LeadOpportunity, LeadSourceSystem  # <-- adjust app name if needed
from clientsetup.models import Project


class MetaZapierOpportunityIngestAPIView(APIView):
    """
    Zapier -> Django (LeadOpportunity) ingest
    Security: X-WEBHOOK-SECRET header (no JWT required)
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # ✅ Zapier ke liye JWT off

    def post(self, request):
        # ---------------------------
        # 1) Security (Secret header)
        # ---------------------------
        incoming = request.headers.get("X-WEBHOOK-SECRET", "")
        expected = getattr(settings, "ZAPIER_META_WEBHOOK_SECRET", "")

        if not expected or not constant_time_compare(incoming, expected):
            return Response({"detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data or {}

        # ---------------------------
        # 2) Required: external_id
        # ---------------------------
        external_id = (payload.get("external_id") or "").strip()
        if not external_id:
            # Tumhare model me external_id blank allowed hai,
            # but for dedupe & id generation, we MUST require it.
            return Response(
                {"ok": False, "detail": "external_id missing. Map REAL Facebook Lead ID (leadgen_id / id)."},
                status=status.HTTP_200_OK,
            )

        # ---------------------------
        # 3) Map fields (accept multiple keys)
        # ---------------------------
        full_name = (payload.get("full_name") or payload.get("name") or "").strip()
        email = (payload.get("email") or "").strip()

        # Zapier me key "mobile" bhi ho sakta, ya "phone"
        mobile_number = (
            (payload.get("mobile_number") or payload.get("mobile") or payload.get("phone") or "").strip()
        )

        source_name = (payload.get("source_name") or payload.get("campaign") or "META Lead Ads").strip()

        # Optional: project mapping (only if Zapier sends project_id)
        project = None
        project_id = payload.get("project_id")
        if project_id:
            project = Project.objects.filter(id=project_id).first()

        # ---------------------------
        # 4) Save / Update (dedupe safe)
        # ---------------------------
        try:
            obj, created = LeadOpportunity.objects.update_or_create(
                source_system=LeadSourceSystem.META,
                external_id=external_id,
                defaults={
                    "source_name": source_name,
                    "full_name": full_name,
                    "email": email,
                    "mobile_number": mobile_number,
                    "raw_payload": payload,
                    "project": project,
                },
            )
        except Exception as e:
            # If unique constraint fails etc.
            return Response({"ok": False, "detail": f"DB_ERROR: {str(e)}"}, status=status.HTTP_200_OK)

        return Response(
            {"ok": True, "created": created, "id": obj.id, "external_id": obj.external_id},
            status=status.HTTP_200_OK,
        )
