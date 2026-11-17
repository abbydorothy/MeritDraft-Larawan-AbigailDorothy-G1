from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("", views.dashboard_redirect, name="dashboard"),
    path("register/", views.register_view, name="register"),
    path("login/", views.MeritLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/student/", views.student_dashboard, name="dashboard_student"),
    path("dashboard/admin/", views.admin_dashboard, name="dashboard_admin"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
]
