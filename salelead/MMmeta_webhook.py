# # salelead/meta_webhook.py
# from django.http import HttpResponse
# from django.conf import settings
# from django.views.decorators.csrf import csrf_exempt
# salelead/meta_webhook.py
import json
import requests
from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

META_GRAPH = "https://graph.facebook.com/v24.0"

@csrf_exempt
def meta_webhook(request):

    # 🔹 Verification (already correct)
    if request.method == "GET":
        if (
            request.GET.get("hub.mode") == "subscribe"
            and request.GET.get("hub.verify_token") == settings.META_WEBHOOK_VERIFY_TOKEN
        ):
            return HttpResponse(
                request.GET.get("hub.challenge"),
                content_type="text/plain",
                status=200,
            )
        return HttpResponse("Invalid token", status=403)

    # 🔹 Lead event
    if request.method == "POST":
        payload = json.loads(request.body)
        print("META PAYLOAD:", payload)

        try:
            entry = payload["entry"][0]
            change = entry["changes"][0]
            value = change["value"]

            leadgen_id = value.get("leadgen_id")
            page_id = value.get("page_id")

            if not leadgen_id:
                return HttpResponse("No leadgen_id", status=200)

            # 🔹 Fetch lead details from Meta
            lead_url = f"{META_GRAPH}/{leadgen_id}"
            params = {
                "access_token": settings.META_WEBHOOK_VERIFY_TOKEN,
                "fields": "created_time,ad_id,ad_name,form_id,field_data"
            }

            res = requests.get(lead_url, params=params)
            lead_data = res.json()

            print("LEAD DATA:", lead_data)

            # 🔹 Send to your CRM ingest API
            crm_url = f"{settings.BACKEND_BASE_URL}/api/sales/integrations/opportunities/META/"

            requests.post(crm_url, json={
                "source": "META",
                "page_id": page_id,
                "leadgen_id": leadgen_id,
                "raw": lead_data
            }, timeout=5)

        except Exception as e:
            print("META ERROR:", str(e))

        return HttpResponse("EVENT_RECEIVED", status=200)

    return HttpResponse("Method not allowed", status=405)


