# costsheet/pdf_utils.py
import logging
from django.core.files.base import ContentFile
from common.pdf_utils import render_html_to_pdf_bytes

log = logging.getLogger(__name__)


def generate_quotation_pdf(costsheet, request=None, force: bool = False):
    """
    Generate (or reuse) quotation PDF for given CostSheet.

    - Uses common.pdf_utils.render_html_to_pdf_bytes (xhtml2pdf)
    - Stores as CostSheetAttachment (label = "Quotation PDF")
    - Returns the attachment instance
    """
    from .models import CostSheetAttachment  # avoid circular import

    # 1) Reuse existing attachment (latest) if not forcing
    try:
        existing = (
            costsheet.attachments
            .filter(label="Quotation PDF")
            .order_by("-id")
            .first()
        )
    except AttributeError:
        # Agar related_name 'attachments' nahi hai to yaha aayega
        existing = None

    if existing and not force:
        return existing

    # 2) Render HTML -> PDF bytes
    context = {
        "quotation": costsheet,
    }

    pdf_bytes = render_html_to_pdf_bytes(
        "costsheet/quotation_pdf.html",
        context,
    )

    if not pdf_bytes:
        # xhtml2pdf fail ho gaya
        raise RuntimeError("Failed to render quotation PDF.")

    # 3) Make attachment like BookingAttachment style
    filename = f"quotation_{costsheet.quotation_no or costsheet.id}.pdf"

    attachment = CostSheetAttachment(
        costsheet=costsheet,
        label="Quotation PDF",
    )
    attachment.file.save(filename, ContentFile(pdf_bytes), save=True)

    return attachment
