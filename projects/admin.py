from django.contrib import admin

from .models import ChangeSubmission, Project, ProjectMembership


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "role", "joined_at")
    list_filter = ("role",)


@admin.register(ChangeSubmission)
class ChangeSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "author", "tag", "status", "points", "created_at")
    list_filter = ("status", "tag")
