# accounts/serializers_users.py
from rest_framework import serializers
from .models import User

class AssignableUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "display_name", "email", "role")

    def get_display_name(self, obj):
        # try full_name / name / or fallback to first+last / username
        return (
            getattr(obj, "full_name", None)
            or f"{(obj.first_name or '').strip()} {(obj.last_name or '').strip()}".strip()
            or obj.username
        )
