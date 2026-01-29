# accounts/views_assignable_users.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import User, Role
from .serializers_users import AssignableUserSerializer
from leadmanage.views import admin_context_id


class AssignableUsersByAdminAPIView(APIView):
    """
    GET /api/accounts/assignable-users/

    Returns all active users created_by this admin,
    excluding KYC team, plus the admin user itself.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        admin_id = admin_context_id(request.user)

        if not admin_id:
            return Response(
                {"detail": "Admin context not found for this user."},
                status=400,
            )

        # base: users created by this admin (or superadmin) and active
        assign_qs = User.objects.filter(
            created_by_id=admin_id,
            is_active=True,
        ).exclude(role=Role.KYC)

        # include the admin user itself
        assign_qs = assign_qs | User.objects.filter(
            id=admin_id,
            is_active=True,
        )

        assign_qs = assign_qs.distinct().order_by("first_name", "id")

        data = AssignableUserSerializer(assign_qs, many=True).data
        return Response({"results": data})
