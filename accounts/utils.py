# accounts/utils.py (ya jaha tum rakho)
from django.conf import settings
from .models import ClientBrand, Role  # adjust import paths


def build_brand_payload_for_user(user, request=None):
    """
    Returns active ClientBrand payload for this user's client (admin),
    or None if not found.
    """

    # Kis admin ke under user aata hai?
    admin_id = getattr(user, "admin_id", None)

    # Agar khud hi ADMIN hai, to uska khud ka brand
    if not admin_id and getattr(user, "role", None) == Role.ADMIN:
        admin_id = user.id

    if not admin_id:
        return None

    brand = ClientBrand.objects.filter(
        admin_id=admin_id,
        is_active=True,
    ).first()

    if not brand:
        return None

    logo_url = None
    if brand.logo:
        if request is not None:
            try:
                logo_url = request.build_absolute_uri(brand.logo.url)
            except Exception:
                logo_url = brand.logo.url
        else:
            logo_url = brand.logo.url

    return {
        "company_name": brand.company_name,
        "logo": logo_url,
        "primary_color": brand.primary_color,
        "secondary_color": brand.secondary_color,
        "background_color": brand.background_color,
        "font_family": brand.font_family,
        "base_font_size": brand.base_font_size,
        "heading_color": brand.heading_color,
        "accent_color": brand.accent_color,
        "button_primary_bg": brand.button_primary_bg,
        "button_primary_text": brand.button_primary_text,
    }



from clientsetup.models import Project
from salelead.utils import _project_ids_for_user  # jaha tumne yeh helper rakha hai

def build_authorized_projects_payload(user):
    """
    Return a small list of projects this user is authorised on.
    Used in /login and /login/otp/verify responses.
    """
    if not user or not user.is_authenticated:
        return []

    project_ids = _project_ids_for_user(user)
    if not project_ids:
        return []

    projects = (
        Project.objects
        .filter(id__in=project_ids)
        .order_by("id")
    )

    payload = []
    for p in projects:
        name = (
            getattr(p, "project_name", None)
            or getattr(p, "name", None)
            or str(p)
        )

        payload.append(
            {
                "id": p.id,
                "name": name,
                # optional extras if tumhare model me ho:
                # "code": getattr(p, "code", None),
                # "rera_no": getattr(p, "rera_no", None),
            }
        )
    return payload
