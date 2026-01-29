# salelead/integrations/normalizers.py

def normalize_meta_webhook(payload: dict) -> dict:
    """
    Supports BOTH:
    1) Real webhook payload: entry[0].changes[0].value
    2) Meta dashboard 'Send to server' sample: {field, value}
    """

    value = {}

    # Case A: Real webhook payload
    try:
        entry = (payload.get("entry") or [])[0]
        change = (entry.get("changes") or [])[0]
        value = change.get("value") or {}
    except Exception:
        pass

    # Case B: Sample payload
    if not value and isinstance(payload.get("value"), dict):
        value = payload.get("value") or {}

    leadgen_id = value.get("leadgen_id") or value.get("lead_id")
    page_id = value.get("page_id")
    form_id = value.get("form_id")
    ad_id = value.get("ad_id")
    created_time = value.get("created_time")
    adgroup_id = value.get("adgroup_id")

    return {
        "external_id": leadgen_id,  # idempotency key
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
