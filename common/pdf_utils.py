# common/pdf_utils.py
from io import BytesIO
from django.template.loader import get_template
from xhtml2pdf import pisa


def render_html_to_pdf_bytes(template_name: str, context: dict) -> bytes | None:
    """
    Render a Django template to PDF bytes using xhtml2pdf.
    Returns bytes or None on error.
    """
    template = get_template(template_name)
    html = template.render(context)

    result = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=result)

    if pisa_status.err:
        return None

    return result.getvalue()
    