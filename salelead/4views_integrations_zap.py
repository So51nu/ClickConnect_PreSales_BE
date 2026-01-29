# salelead/views_integrations_zap.py
import json
import re

from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from salelead.models import LeadOpportunity, LeadSourceSystem
from clientsetup.models import Project

User = get_user_model()


def _to_str(v):
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def _clean_mobile(v) -> str:
    """
    DB safe:
    - keep digits and +
    - max 32 chars (because model field max_length=32)
    """
    s = _to_str(v).strip()
    if not s:
        return ""
    s = re.sub(r"[^\d+]", "", s)   # keep only digits and +
    return s[:32]


class MetaZapierOpportunityIngestAPIView(APIView):
    """
    Zapier -> Django (LeadOpportunity) ingest
    Security: X-WEBHOOK-SECRET header (no JWT required)
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # 1) Security
        incoming = request.headers.get("X-WEBHOOK-SECRET", "")
        expected = getattr(settings, "ZAPIER_META_WEBHOOK_SECRET", "")
        if not expected or not constant_time_compare(incoming, expected):
            return Response({"ok": False, "detail": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data or {}

        # 2) Required: external_id
        external_id = _to_str(payload.get("external_id")).strip()
        if not external_id:
            return Response(
                {"ok": False, "detail": "external_id missing. Map REAL Facebook Lead ID (leadgen_id / ID)."},
                status=status.HTTP_200_OK,
            )

        # 3) Map fields
        full_name = _to_str(payload.get("full_name") or payload.get("name")).strip()
        email = _to_str(payload.get("email")).strip()

        mobile_number = _clean_mobile(
            payload.get("mobile_number") or payload.get("mobile") or payload.get("phone")
        )

        source_name = _to_str(payload.get("source_name") or payload.get("campaign") or "META Lead Ads").strip()

        # 4) OPTIONAL: project mapping
        project = None
        project_id = payload.get("project_id")
        if project_id:
            project = Project.objects.filter(id=project_id).first()

        # 5) OPTIONAL: owner mapping (LeadOpportunity.owner)
        owner = None
        owner_id = payload.get("owner_id") or payload.get("assign_to_id")
        owner_email = _to_str(payload.get("owner_email") or payload.get("assign_to_email")).strip()

        if owner_id:
            owner = User.objects.filter(id=owner_id).first()
        elif owner_email:
            owner = User.objects.filter(email__iexact=owner_email).first()

        # 6) Save / Update
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
                    "project": project,   # optional
                    "owner": owner,       # optional
                },
            )
        except Exception as e:
            return Response({"ok": False, "detail": f"DB_ERROR: {str(e)}"}, status=status.HTTP_200_OK)

        return Response(
            {"ok": True, "created": created, "id": obj.id, "external_id": obj.external_id},
            status=status.HTTP_200_OK,
        )
