# salelead/integrations/views.py

import json
import requests
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from salelead.models import LeadOpportunity  # adjust if your app name differs

META_GRAPH = "https://graph.facebook.com/v24.0"


def normalize_meta_webhook(payload: dict) -> dict:
    value = {}

    # Case A: Real webhook payload
    try:
        entry = (payload.get("entry") or [])[0]
        change = (entry.get("changes") or [])[0]
        value = change.get("value") or {}
    except Exception:
        pass

    # Case B: Meta dashboard sample payload: {field, value}
    if not value and isinstance(payload.get("value"), dict):
        value = payload.get("value") or {}

    leadgen_id = value.get("leadgen_id") or value.get("lead_id")
    page_id = value.get("page_id")
    form_id = value.get("form_id")
    ad_id = value.get("ad_id")
    created_time = value.get("created_time")
    adgroup_id = value.get("adgroup_id")

    return {
        "external_id": leadgen_id,
        "source_system": "META",
        "data": {
            "leadgen_id": leadgen_id,
            "page_id": page_id,
            "form_id": form_id,
            "ad_id": ad_id,
            "adgroup_id": adgroup_id,
            "created_time": created_time,
        },
    }


def extract_contact_from_field_data(field_data):
    full_name = ""
    email = ""
    phone = ""

    if not isinstance(field_data, list):
        return full_name, email, phone

    def first_val(item):
        vals = item.get("values") or []
        if isinstance(vals, list) and vals:
            return str(vals[0]).strip()
        return ""

    for item in field_data:
        name = str(item.get("name") or "").strip().lower()
        val = first_val(item)
        if not val:
            continue

        if name in ("full_name", "name"):
            full_name = full_name or val
        elif name in ("email", "email_address"):
            email = email or val
        elif name in ("phone_number", "phone", "mobile", "mobile_number"):
            phone = phone or val

    return full_name, email, phone


def fetch_meta_lead_details_if_possible(leadgen_id: str) -> dict:
    """
    If META_SYSTEM_USER_TOKEN exists -> fetch lead details.
    If not -> return {} (no error, because we still want to save DB).
    """
    token = getattr(settings, "META_SYSTEM_USER_TOKEN", None)
    if not token:
        return {}

    url = f"{META_GRAPH}/{leadgen_id}"
    params = {
        "access_token": token,
        "fields": "created_time,ad_id,ad_name,form_id,page_id,field_data",
    }

    try:
        res = requests.get(url, params=params, timeout=6)
        try:
            return res.json()
        except Exception:
            return {"error": {"message": f"Non-JSON response status={res.status_code}", "body": res.text[:300]}}
    except Exception as e:
        return {"error": {"message": str(e)}}


@api_view(["GET", "POST"])
@authentication_classes([])  # no CSRF/session for webhook
@permission_classes([AllowAny])
def ingest_opportunity(request, source_system: str):
    source_system = (source_system or "").upper().strip()

    # === HARD LOG: prove hit ===
    try:
        raw_body = request.body.decode("utf-8", errors="ignore")
        with open("/tmp/meta_hits.log", "a") as f:
            f.write(
                f"{timezone.now()} HIT method={request.method} "
                f"path={request.get_full_path()} "
                f"ip={request.META.get('REMOTE_ADDR')} "
                f"xff={request.META.get('HTTP_X_FORWARDED_FOR','')} "
                f"ct={request.META.get('CONTENT_TYPE','')}\n"
            )
            if request.method == "GET":
                f.write("GET params: " + json.dumps(dict(request.GET), default=str) + "\n\n")
            else:
                f.write("RAW_BODY: " + (raw_body[:8000] if raw_body else "<empty>") + "\n\n")
    except Exception:
        pass

    if source_system != "META":
        return Response({"detail": "Unknown source"}, status=400)

    # === Verification ===
    if request.method == "GET":
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == settings.META_WEBHOOK_VERIFY_TOKEN:
            return HttpResponse(challenge or "", content_type="text/plain", status=200)

        return Response({"detail": "Meta verification failed"}, status=403)

    # === POST webhook ===
    payload = request.data if isinstance(request.data, dict) else {}
    normalized = normalize_meta_webhook(payload)
    leadgen_id = (normalized.get("external_id") or "").strip()

    # If no lead id, still ACK
    if not leadgen_id:
        return Response({"ok": True, "detail": "No leadgen_id"}, status=200)

    # Try fetch lead details only if token exists
    lead_details = fetch_meta_lead_details_if_possible(leadgen_id)

    # Extract contact if details present
    full_name = email = phone = ""
    if isinstance(lead_details, dict) and lead_details.get("field_data"):
        full_name, email, phone = extract_contact_from_field_data(lead_details.get("field_data"))

    # ✅ Save to LeadOpportunity always
    try:
        opp, created = LeadOpportunity.objects.update_or_create(
            source_system="META",
            external_id=leadgen_id,
            defaults={
                "source_name": "META Lead Ads",
                "full_name": full_name or "",
                "email": email or "",
                "mobile_number": phone or "",
                "raw_payload": {
                    "webhook": payload,
                    "normalized": normalized,
                    "lead_details": lead_details,  # {} if no token
                },
            },
        )

        try:
            with open("/tmp/meta_hits.log", "a") as f:
                f.write(f"{timezone.now()} SAVED LeadOpportunity id={opp.id} created={created} external_id={leadgen_id}\n\n")
        except Exception:
            pass

    except Exception as e:
        try:
            with open("/tmp/meta_hits.log", "a") as f:
                f.write(f"{timezone.now()} SAVE_ERROR external_id={leadgen_id} err={str(e)}\n\n")
        except Exception:
            pass

        # Still ACK 200 to Meta
        return Response({"ok": True, "detail": "Save failed but ACK sent"}, status=200)

    return Response(
        {"ok": True, "saved": True, "external_id": leadgen_id, "db_id": opp.id},
        status=200,
    )
