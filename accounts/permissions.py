# accounts/permissions.py (ya jaha rakhte ho)
from rest_framework import permissions
from .models import Role

class IsKycUser(permissions.BasePermission):
    """
    Only KYC role can use the KYC payment API.
    """
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return getattr(user, "role", None) == Role.KYC
