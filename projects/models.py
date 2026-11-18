from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Count, Sum
from django.urls import reverse

from .diffing import ADDITION, REVISION, compare


class Project(models.Model):
    """A group paper. The official text only changes through approved changes."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    current_text = models.TextField("official text")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_projects"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("projects:detail", args=[self.pk])

    def leaderboard(self):
        """Per-project ranking: points come only from APPROVED changes made in THIS project."""
        totals = {
            row["author_id"]: row
            for row in self.changes.filter(status=ChangeSubmission.Status.APPROVED)
            .values("author_id")
            .annotate(total=Sum("points"), count=Count("id"))
        }
        rows = []
        for membership in self.memberships.select_related("user"):
            t = totals.get(membership.user_id)
            rows.append({
                "membership": membership,
                "points": t["total"] if t else Decimal("0"),
                "approved": t["count"] if t else 0,
            })
        rows.sort(key=lambda r: (-r["points"], r["membership"].user.username.lower()))
        rank, previous = 0, None
        for position, row in enumerate(rows, start=1):
            if row["points"] != previous:
                rank, previous = position, row["points"]
            row["rank"] = rank
        return rows


class ProjectMembership(models.Model):
    """A user's role inside ONE project - the same user can lead one project and be a member of another."""

    class Role(models.TextChoices):
        LEADER = "leader", "Leader"
        MEMBER = "member", "Member"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="unique_member_per_project")]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} - {self.project} ({self.get_role_display()})"

    @property
    def is_leader(self):
        return self.role == self.Role.LEADER


class ChangeSubmission(models.Model):
    class Tag(models.TextChoices):
        ADDITION = ADDITION, "Addition (1 pt/word)"
        REVISION = REVISION, "Revision (0.5 pt/word)"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="changes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    base_text = models.TextField(help_text="Official text at the time of submission (used for the diff).")
    proposed_text = models.TextField("your edited version")
    tag = models.CharField(max_length=10, choices=Tag.choices)
    note = models.CharField("short note (optional)", max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_changes"
    )
    review_note = models.CharField(max_length=500, blank=True)
    points = models.DecimalField(max_digits=8, decimal_places=1, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Change #{self.pk} on {self.project} by {self.author}"

    def get_absolute_url(self):
        return reverse("projects:change_detail", args=[self.pk])

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_stale(self):
        """True when the official text changed after this was submitted."""
        return self.is_pending and self.project.current_text != self.base_text

    def diff(self):
        return compare(self.base_text, self.proposed_text)
