# salelead/tasks_integration.py

from celery import shared_task
from .gsheets import fetch_google_sheet_rows
from .normalizers import normalize_google_sheet
from .serializers import LeadOpportunityIngestSerializer
from .models import LeadSourceSystem


@shared_task
def sync_google_sheet_opportunities():
    """
    Google Sheet se rows laata hai aur LeadOpportunity me
    NEW / UPDATE karta hai via LeadOpportunityIngestSerializer.
    """
    rows = fetch_google_sheet_rows()
    created = 0
    updated = 0

    for row in rows:
        normalized = normalize_google_sheet(row)

        ser = LeadOpportunityIngestSerializer(
            data=normalized,
            context={
                "source_system": LeadSourceSystem.GOOGLE_SHEET,
                "request": None,  # Celery se aa raha hai, HTTP request nahi
            },
        )

        if not ser.is_valid():
            print("Row invalid:", ser.errors, "row:", row)
            continue

        opp = ser.save()
        if getattr(ser, "_created", False):
            created += 1
        else:
            updated += 1

    return {"created": created, "updated": updated}
