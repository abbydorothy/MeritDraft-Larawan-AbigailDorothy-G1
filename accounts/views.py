from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render

from .decorators import role_required
from .forms import LoginForm, ProfileForm, RegistrationForm
from .models import User
from projects.models import ChangeSubmission, Project, ProjectMembership


def register_view(request):
    if request.user.is_authenticated:
        return redirect(request.user.dashboard_url)
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Account created for {user.username}. You can now log in.")
            return redirect("accounts:login")
        messages.error(request, "Registration failed. Please fix the errors below.")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class MeritLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().display_name}!")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Login failed. Check your credentials.")
        return super().form_invalid(form)

    def get_success_url(self):
        # Honour ?next= if safe, otherwise send the user to their own role dashboard.
        return self.get_redirect_url() or self.request.user.dashboard_url


@login_required
def dashboard_redirect(request):
    return redirect(request.user.dashboard_url)


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    user = request.user
    memberships = ProjectMembership.objects.filter(user=user).select_related("project")
    # Points are per project: sum of THIS user's approved changes, grouped by project.
    points = {
        r["project_id"]: r["total"]
        for r in ChangeSubmission.objects.filter(author=user, status=ChangeSubmission.Status.APPROVED)
        .values("project_id").annotate(total=Sum("points"))
    }
    leader_ids = [m.project_id for m in memberships if m.is_leader]
    to_review = {
        r["project_id"]: r["n"]
        for r in ChangeSubmission.objects.filter(project_id__in=leader_ids, status=ChangeSubmission.Status.PENDING)
        .exclude(author=user).values("project_id").annotate(n=Count("id"))
    }
    rows = [
        {"project": m.project, "role": m.role, "points": points.get(m.project_id, 0), "to_review": to_review.get(m.project_id, 0)}
        for m in memberships
    ]
    context = {
        "rows": rows,
        "to_review": sum(to_review.values()),
        "my_pending": user.submissions.filter(status=ChangeSubmission.Status.PENDING).count(),
        "recent": user.submissions.select_related("project")[:5],
    }
    return render(request, "accounts/dashboard_student.html", context)


@role_required(User.Role.INSTRUCTOR)
def instructor_dashboard(request):
    S = ChangeSubmission.Status
    projects = Project.objects.annotate(
        member_count=Count("memberships", distinct=True),
        approved_count=Count("changes", filter=Q(changes__status=S.APPROVED), distinct=True),
        pending_count=Count("changes", filter=Q(changes__status=S.PENDING), distinct=True),
        rejected_count=Count("changes", filter=Q(changes__status=S.REJECTED), distinct=True),
    ).order_by("name")
    context = {
        "projects": projects,
        "approved_total": ChangeSubmission.objects.filter(status=S.APPROVED).count(),
        "pending_total": ChangeSubmission.objects.filter(status=S.PENDING).count(),
    }
    return render(request, "accounts/dashboard_instructor.html", context)


@role_required(User.Role.INSTRUCTOR)
def instructor_dashboard(request):
    return render(request, "accounts/dashboard_instructor.html")


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    counts = {
        "students": User.objects.filter(role=User.Role.STUDENT).count(),
        "instructors": User.objects.filter(role=User.Role.INSTRUCTOR).count(),
        "admins": User.objects.filter(role=User.Role.ADMIN).count(),
        "total": User.objects.count(),
        "projects": Project.objects.count(),
    }
    recent = User.objects.order_by("-date_joined")[:5]
    return render(request, "accounts/dashboard_admin.html", {"counts": counts, "recent": recent})


@login_required
def profile_view(request):
    # Always the logged-in user's own profile -- no user id in the URL.
    return render(request, "accounts/profile.html", {"profile_user": request.user})


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")
        messages.error(request, "Could not update profile. Please fix the errors below.")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})
