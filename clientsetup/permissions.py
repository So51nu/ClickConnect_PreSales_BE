from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsStaffOrAdminForUnsafe(BasePermission):
    """
    Allow only staff or admins to POST/PUT/PATCH/DELETE.
    Everyone authenticated can GET (you can tighten later).
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        u = request.user
        if not (u and u.is_authenticated):
            return False
        return u.is_staff or getattr(u, "role", None) == "ADMIN"
