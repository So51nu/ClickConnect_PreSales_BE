# accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User,ClientBrand,ProjectUserAccess

admin.site.register(ClientBrand)




# accounts/admin.py
from django.contrib import admin
from .models import ProjectUserAccess

@admin.register(ProjectUserAccess)
class ProjectUserAccessAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "is_active", "can_view", "can_edit")
    list_filter = ("is_active", "can_view", "can_edit", "project")
    search_fields = ("user__username", "user__email", "project__project_name")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin for our User model with role + admin (owner) + created_by.
    """

    list_display = (
        "username",
        "email",
        "role",
        "admin",        # owning admin for RECEPTION/SALES/CP/CALLING_TEAM
        "created_by",
        "is_active",
        "is_staff",
        "is_superuser",
"signature",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    # Detail page layout
    fieldsets = (
        (None, {"fields": ("username", "password", "signature")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (
            _("Business Fields"),
            {
                "fields": (
                    "role",
                    "admin",        # FK to User with role=ADMIN
                    "created_by",   # who created this user
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    # Add user form (when you click "Add user" in admin)
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "role",
                    "admin",      # for non-admin roles, select owning ADMIN
"signature",
                ),
            },
        ),
    )

    raw_id_fields = ("admin", "created_by")

    def save_model(self, request, obj, form, change):
        """
        Automatically set created_by for newly created users
        if not already set.
        """
        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
