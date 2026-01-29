# salelead/views_integration.py

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import LeadSourceSystem
from .normalizers import (
    normalize_web_form,
    normalize_meta,
    normalize_google_sheet,
    normalize_portal,
)
from .serializers import LeadOpportunityIngestSerializer

NORMALIZERS = {
    "WEB_FORM": normalize_web_form,
    "META": normalize_meta,
    "GOOGLE_SHEET": normalize_google_sheet,
    "PORTAL": normalize_portal,
}


def _create_or_update_from_normalized(
    source_system: str,
    normalized: dict,
    raw_payload: dict | None = None,
    request=None,
):
    """
    SINGLE place jo normalized dict se LeadOpportunity create/update karega.
    - Celery tasks yahi use karenge
    - Webhook view (ingest_opportunity) bhi yahi use karega
    """
    # copy so we don't mutate original
    data = dict(normalized)

    # agar normalizer ne raw_payload nahi diya, to yaha se inject kar do
    if raw_payload is not None and "raw_payload" not in data:
        data["raw_payload"] = raw_payload

    serializer = LeadOpportunityIngestSerializer(
        data=data,
        context={
            "request": request,
            "source_system": source_system,
        },
    )
    serializer.is_valid(raise_exception=True)
    opp = serializer.save()
    created = getattr(serializer, "_created", False)
    return opp, created


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def ingest_opportunity(request, source_system):
    source_system = source_system.upper()
    if source_system not in LeadSourceSystem.values:
        return Response(
            {"detail": f"Unknown source system '{source_system}'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 1️⃣ Meta verification (GET)
    if request.method == "GET" and source_system == "META":
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == settings.META_WEBHOOK_VERIFY_TOKEN:
            # Facebook expects plain 200 + challenge
            return Response(challenge, status=status.HTTP_200_OK)
        else:
            return Response(
                {"detail": "Verification failed"},
                status=status.HTTP_403_FORBIDDEN,
            )

    # 2️⃣ Baaki sab ke liye POST data ingest
    if request.method != "POST":
        return Response(
            {"detail": "Only POST allowed for this source."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    normalizer = NORMALIZERS.get(source_system)
    if not normalizer:
        return Response(
            {"detail": f"No normalizer defined for '{source_system}'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # raw → normalized
    normalized = normalizer(request.data or {})

    # 🔁 yahi helper Celery bhi use karega
    opp, created = _create_or_update_from_normalized(
        source_system=source_system,
        normalized=normalized,
        raw_payload=request.data,
        request=request,
    )

    return Response(
        {
            "id": opp.id,
            "created": created,
            "status": opp.status,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )
