# common/tenancy.py
from rest_framework.exceptions import PermissionDenied
from salelead.utils import _project_ids_for_user


def get_allowed_project_ids(user):
    """
    Single source of truth for project access.
    """
    return _project_ids_for_user(user)


def assert_project_allowed(request, project_id):
    """
    Raise 403 if user cannot access this project_id.
    """
    try:
        pid = int(project_id)
    except Exception:
        raise PermissionDenied("Invalid project_id.")

    allowed = set(get_allowed_project_ids(request.user))
    if pid not in allowed:
        raise PermissionDenied("You are not allowed to access this project.")


def filter_qs_by_projects(qs, user, project_field="project_id"):
    """
    Apply allowed-project filter to any queryset.
    """
    allowed_ids = get_allowed_project_ids(user)
    return qs.filter(**{f"{project_field}__in": allowed_ids})
