from rest_framework import serializers
from .models import ProjectUserAccess  # adjust path


class ProjectUserAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectUserAccess
        fields = ["id", "project", "can_view", "can_edit", "is_active"]

