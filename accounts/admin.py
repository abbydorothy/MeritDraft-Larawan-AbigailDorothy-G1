from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class MeritUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "date_joined")
    list_filter = ("role", "is_staff", "is_superuser")
    fieldsets = UserAdmin.fieldsets + (("MeritDraft", {"fields": ("role", "contact_number", "profile_photo")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("MeritDraft", {"fields": ("email", "role")}),)

    def get_readonly_fields(self, request, obj=None):
        # Only an existing admin (superuser) may change anyone's role, so only they can create new admins.
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.append("role")
        return readonly
