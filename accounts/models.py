from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class User(AbstractUser):
    """MeritDraft user. The account role is global (Admin, Instructor or Student).
    Per-project roles (Leader / Member) are stored on a project-membership
    model, added in the project-setup phase."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        INSTRUCTOR = "instructor", "Instructor"
        STUDENT = "student", "Student"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    contact_number = models.CharField(max_length=20, blank=True)
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        # Admin is a special role: role "admin" always carries Django admin access,
        # and any superuser is always an admin.
        if self.role == self.Role.ADMIN:
            self.is_staff = True
            self.is_superuser = True
        elif self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def dashboard_url(self):
        return reverse(f"accounts:dashboard_{self.role}")

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def can_view_all_projects(self):
        """Instructors and admins get a read-only view of every project."""
        return self.role in (self.Role.INSTRUCTOR, self.Role.ADMIN)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
