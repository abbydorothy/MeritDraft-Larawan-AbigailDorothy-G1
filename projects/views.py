from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .diffing import calculate_points, compare
from .forms import AddMemberForm, ChangeForm, ProjectForm
from .models import ChangeSubmission, Project, ProjectMembership

Role = ProjectMembership.Role
Status = ChangeSubmission.Status


# ---------------------------------------------------------------- helpers
def _get_project(user, pk):
    """Return (project, membership). Non-members get 403 unless they are an instructor/admin (read-only)."""
    project = get_object_or_404(Project, pk=pk)
    membership = ProjectMembership.objects.filter(project=project, user=user).first()
    if membership is None and not user.can_view_all_projects:
        raise PermissionDenied
    return project, membership


def _require_leader(membership):
    if membership is None or not membership.is_leader:
        raise PermissionDenied


def _flash_form_errors(request, form):
    for errors in form.errors.values():
        for error in errors:
            messages.error(request, error)


def _leader_count(project):
    return ProjectMembership.objects.filter(project=project, role=Role.LEADER).count()


# ---------------------------------------------------------------- projects
@login_required
def project_list(request):
    user = request.user
    if user.can_view_all_projects:
        projects = Project.objects.all()
    else:
        mine = ProjectMembership.objects.filter(user=user).values("project_id")
        projects = Project.objects.filter(pk__in=mine)
    projects = projects.annotate(
        member_count=Count("memberships", distinct=True),
        pending_count=Count("changes", filter=Q(changes__status=Status.PENDING), distinct=True),
    ).order_by("-created_at")
    roles = dict(ProjectMembership.objects.filter(user=user).values_list("project_id", "role"))
    projects = list(projects)
    for p in projects:
        p.my_role = roles.get(p.pk)
    return render(request, "projects/project_list.html", {"projects": projects})


@role_required(User.Role.STUDENT)
def project_create(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            with transaction.atomic():
                project = form.save(commit=False)
                project.created_by = request.user
                project.save()
                ProjectMembership.objects.create(project=project, user=request.user, role=Role.LEADER)
            messages.success(request, f'Project "{project.name}" created. You are its Leader.')
            return redirect(project)
        messages.error(request, "Could not create the project. Please fix the errors below.")
    return render(request, "projects/project_form.html", {"form": form, "heading": "New project"})


@login_required
def project_detail(request, pk):
    project, membership = _get_project(request.user, pk)
    is_leader = bool(membership and membership.is_leader)
    changes = project.changes.select_related("author", "reviewer")
    context = {
        "project": project,
        "membership": membership,
        "is_leader": is_leader,
        "leaderboard": project.leaderboard(),
        "changes": changes,
        "pending_count": changes.filter(status=Status.PENDING).count(),
        "add_form": AddMemberForm(project=project) if is_leader else None,
    }
    return render(request, "projects/project_detail.html", context)


@login_required
def project_edit(request, pk):
    project, membership = _get_project(request.user, pk)
    _require_leader(membership)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated.")
            return redirect(project)
        messages.error(request, "Could not update the project. Please fix the errors below.")
    return render(request, "projects/project_form.html", {"form": form, "heading": f"Edit {project.name}"})


@login_required
def project_delete(request, pk):
    project, membership = _get_project(request.user, pk)
    _require_leader(membership)
    if request.method == "POST":
        name = project.name
        project.delete()
        messages.success(request, f'Project "{name}" and all its changes were deleted.')
        return redirect("projects:list")
    return render(request, "projects/project_confirm_delete.html", {"project": project})


# ---------------------------------------------------------------- members
@login_required
@require_POST
def member_add(request, pk):
    project, membership = _get_project(request.user, pk)
    _require_leader(membership)
    form = AddMemberForm(request.POST, project=project)
    if form.is_valid():
        ProjectMembership.objects.create(project=project, user=form.user, role=form.cleaned_data["role"])
        messages.success(request, f"{form.user.username} was added as {form.cleaned_data['role'].title()}.")
    else:
        _flash_form_errors(request, form)
    return redirect(project)


@login_required
@require_POST
def member_remove(request, pk, member_id):
    project, membership = _get_project(request.user, pk)
    _require_leader(membership)
    target = get_object_or_404(ProjectMembership, pk=member_id, project=project)
    if target.is_leader and _leader_count(project) == 1:
        messages.error(request, "A project must keep at least one Leader. Promote someone else first.")
        return redirect(project)
    # Their unreviewed changes go away with them; approved history and points stay.
    ChangeSubmission.objects.filter(project=project, author=target.user, status=Status.PENDING).delete()
    username = target.user.username
    target.delete()
    messages.success(request, f"{username} was removed from the project.")
    if target.user_id == request.user.id:
        return redirect("projects:list")
    return redirect(project)


@login_required
@require_POST
def member_role(request, pk, member_id):
    project, membership = _get_project(request.user, pk)
    _require_leader(membership)
    target = get_object_or_404(ProjectMembership, pk=member_id, project=project)
    if target.is_leader:
        if _leader_count(project) == 1:
            messages.error(request, "A project must keep at least one Leader. Promote someone else first.")
            return redirect(project)
        target.role = Role.MEMBER
    else:
        target.role = Role.LEADER
    target.save(update_fields=["role"])
    messages.success(request, f"{target.user.username} is now a {target.get_role_display()}.")
    return redirect(project)


# ---------------------------------------------------------------- changes
@login_required
def change_create(request, pk):
    project, membership = _get_project(request.user, pk)
    if membership is None:
        raise PermissionDenied  # instructors/admins are read-only
    form = ChangeForm(request.POST or None, project=project, initial={"proposed_text": project.current_text})
    if request.method == "POST":
        if form.is_valid():
            change = form.save(commit=False)
            change.project, change.author, change.base_text = project, request.user, project.current_text
            change.save()
            messages.success(request, "Change submitted for review.")
            return redirect(change)
        messages.error(request, "Could not submit the change. Please fix the errors below.")
    return render(request, "projects/change_form.html", {"form": form, "project": project, "heading": "Submit a change"})


@login_required
def change_detail(request, pk):
    change = get_object_or_404(ChangeSubmission.objects.select_related("project", "author", "reviewer"), pk=pk)
    project, membership = _get_project(request.user, change.project_id)
    result = change.diff()
    is_leader = bool(membership and membership.is_leader)
    is_author = change.author_id == request.user.id
    context = {
        "change": change,
        "project": project,
        "segments": result["segments"],
        "added": result["added"],
        "removed": result["removed"],
        "preview_points": calculate_points(change.tag, result["added"]),
        "can_review": change.is_pending and is_leader and not is_author,
        "needs_other_leader": change.is_pending and is_leader and is_author,
        "can_edit": change.is_pending and is_author and membership is not None,
    }
    return render(request, "projects/change_detail.html", context)


@login_required
def change_edit(request, pk):
    change = get_object_or_404(ChangeSubmission.objects.select_related("project"), pk=pk)
    project, membership = _get_project(request.user, change.project_id)
    if change.author_id != request.user.id or not change.is_pending or membership is None:
        raise PermissionDenied
    stale = change.is_stale
    # If the official text moved on, start from the latest text so nobody's approved work is overwritten.
    initial = {"proposed_text": project.current_text} if stale else None
    form = ChangeForm(request.POST or None, instance=change, project=project, initial=initial)
    if request.method == "POST":
        if form.is_valid():
            change = form.save(commit=False)
            change.base_text = project.current_text
            change.save()
            messages.success(request, "Change updated.")
            return redirect(change)
        messages.error(request, "Could not update the change. Please fix the errors below.")
    context = {
        "form": form, "project": project, "heading": "Edit your change",
        "stale": stale, "old_proposed": change.proposed_text if stale else "",
    }
    return render(request, "projects/change_form.html", context)


@login_required
@require_POST
def change_delete(request, pk):
    change = get_object_or_404(ChangeSubmission, pk=pk)
    project, membership = _get_project(request.user, change.project_id)
    if change.author_id != request.user.id or not change.is_pending:
        raise PermissionDenied
    change.delete()
    messages.success(request, "Change deleted.")
    return redirect(project)


@login_required
@require_POST
def change_review(request, pk):
    change = get_object_or_404(ChangeSubmission, pk=pk)
    project, membership = _get_project(request.user, change.project_id)
    _require_leader(membership)
    if change.author_id == request.user.id:
        raise PermissionDenied  # nobody reviews their own work
    decision = request.POST.get("decision")
    note = request.POST.get("review_note", "").strip()[:500]
    if decision not in ("approve", "reject"):
        messages.error(request, "Choose Approve or Reject.")
        return redirect(change)
    if decision == "reject" and not note:
        messages.error(request, "Please give a reason when rejecting a change.")
        return redirect(change)

    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=change.project_id)
        change = ChangeSubmission.objects.select_for_update().get(pk=pk)
        if change.status != Status.PENDING:
            messages.error(request, "This change was already reviewed.")
            return redirect(change)
        if decision == "approve":
            if project.current_text != change.base_text:
                messages.error(
                    request,
                    "The official text changed since this was submitted, so it cannot be merged safely. "
                    "Ask the author to edit and resubmit it.",
                )
                return redirect(change)
            result = compare(change.base_text, change.proposed_text)
            change.points = calculate_points(change.tag, result["added"])
            change.status = Status.APPROVED
            project.current_text = change.proposed_text
            project.save(update_fields=["current_text", "updated_at"])
        else:
            change.status = Status.REJECTED
        change.reviewer, change.review_note, change.reviewed_at = request.user, note, timezone.now()
        change.save()

    if change.status == Status.APPROVED:
        messages.success(request, f"Change approved and merged. {change.author.username} earned {change.points} points.")
    else:
        messages.success(request, "Change rejected.")
    return redirect(change)


@role_required(User.Role.STUDENT)
def my_changes(request):
    submissions = request.user.submissions.select_related("project")
    return render(request, "projects/my_changes.html", {"submissions": submissions})
