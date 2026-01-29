# salelead/meta_webhook.py
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def meta_webhook(request):

    if request.method == "POST":
        try:
            payload = json.loads(request.body)
            print("INCOMING PAYLOAD:", payload)

            # ✅ ZAPIER PAYLOAD
            if payload.get("source") == "zapier":
                leadgen_id = payload.get("external_id")

                if not leadgen_id:
                    return HttpResponse("No external_id", status=200)

                from salelead.models import LeadOpportunity, LeadSourceSystem

                obj, created = LeadOpportunity.objects.update_or_create(
                    source_system=LeadSourceSystem.META,   # ✅ FIXED
                    external_id=leadgen_id,
                    defaults={
                        "source_name": "META Lead Ads",
                        "full_name": payload.get("full_name", ""),
                        "email": payload.get("email", ""),
                        "mobile_number": payload.get("mobile", ""),
                        "raw_payload": payload,
                    }
                )

                print("LEAD SAVED:", obj.id, "CREATED:", created)
                return HttpResponse("ZAPIER_LEAD_SAVED", status=200)

            return HttpResponse("IGNORED", status=200)

        except Exception as e:
            print("WEBHOOK ERROR:", str(e))
            return HttpResponse("ERROR", status=500)

    return HttpResponse("METHOD NOT ALLOWED", status=405)
