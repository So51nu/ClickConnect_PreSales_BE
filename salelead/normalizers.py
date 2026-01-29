# salelead/normalizers.py

def normalize_web_form(payload: dict) -> dict:
    """
    Website form / custom frontend se aane wala data.
    """
    source_lead_id = (
        payload.get("source_lead_id")
        or payload.get("form_submission_id")
        or ""
    )
    external_id = payload.get("external_id") or source_lead_id

    return {
        "full_name": payload.get("name") or payload.get("full_name") or "",
        "email": payload.get("email") or "",
        "mobile_number": payload.get("phone") or payload.get("mobile_number") or "",
        "project_id": payload.get("project_id"),  # direct DB id
        "source_name": payload.get("form_name") or "Website Form",
        "source_lead_id": source_lead_id,
        "external_id": external_id,
        "raw_payload": payload,
    }


def normalize_meta(payload: dict) -> dict:
    """
    Meta / Facebook leadgen ke liye normalizer.
    Do mode support karta hai:
    1) Dev / Postman JSON (tum jo abhi bhej rahe ho)
    2) Real webhook (entry[0].changes[0].value...)
    """

    # ---------- 1) DEV MODE (simple JSON jis me full_name, source_lead_id, project_id hai) ----------
    if (
        "full_name" in payload
        or "source_lead_id" in payload
        or "project_id" in payload
    ):
        source_lead_id = (
            payload.get("source_lead_id")
            or payload.get("leadgen_id")
            or payload.get("id")
            or ""
        )
        external_id = payload.get("external_id") or source_lead_id

        return {
            "full_name": payload.get("full_name") or payload.get("name") or "",
            "email": payload.get("email") or "",
            "mobile_number": payload.get("mobile_number") or payload.get("phone") or "",
            "project_id": payload.get("project_id"),
            "source_lead_id": source_lead_id,
            "external_id": external_id,
            "raw_payload": payload.get("raw_payload") or payload,
        }

    # ---------- 2) REAL WEBHOOK MODE ----------
    # typical: payload["entry"][0]["changes"][0]["value"]
    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        value = payload

    full_name = value.get("full_name") or value.get("name", "")
    email = value.get("email", "")
    phone = value.get("phone_number", "") or value.get("phone", "")

    source_lead_id = (
        value.get("source_lead_id")
        or value.get("leadgen_id")
        or value.get("id")
        or ""
    )

    project_id = value.get("project_id")

    return {
        "full_name": full_name,
        "email": email,
        "mobile_number": phone,
        "project_id": project_id,
        "source_lead_id": source_lead_id,
        "external_id": source_lead_id,
        "raw_payload": payload,
    }


def normalize_google_sheet(row: dict) -> dict:
    """
    Google Sheet row → ingest format.
    Column names tum apne sheet ke hisaab se change kar sakte ho.
    """
    source_lead_id = (
        row.get("LeadId")
        or row.get("RowId")
        or row.get("SheetRowId")
        or ""
    )
    external_id = row.get("external_id") or source_lead_id

    return {
        "full_name": row.get("Name", "") or row.get("Full Name", ""),
        "email": row.get("Email", ""),
        "mobile_number": row.get("Phone", "") or row.get("Mobile", ""),
        "project_id": row.get("ProjectId") or row.get("project_id"),
        "source_lead_id": source_lead_id,
        "external_id": external_id,
        "raw_payload": row,
    }


def normalize_portal(payload: dict) -> dict:
    """
    Portals (MagicBricks / 99acres / Housing) ke liye.
    """
    source_lead_id = payload.get("source_lead_id") or payload.get("lead_id") or ""
    external_id = payload.get("external_id") or source_lead_id

    return {
        "full_name": payload.get("name") or "",
        "email": payload.get("email") or "",
        "mobile_number": payload.get("phone") or payload.get("mobile_number") or "",
        "project_id": payload.get("project_id"),
        "source_name": payload.get("portal") or "Portal",
        
        "source_lead_id": source_lead_id,
        "external_id": external_id,
        "raw_payload": payload,
    }
