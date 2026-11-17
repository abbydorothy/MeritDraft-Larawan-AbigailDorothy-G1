from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class MeritUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "date_joined")
    list_filter = ("role", "is_staff", "is_superuser")
    fieldsets = UserAdmin.fieldsets + (("MeritDraft", {"fields": ("role", "contact_number", "profile_photo")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("MeritDraft", {"fields": ("email", "role")}),)
