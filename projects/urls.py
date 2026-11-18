from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("new/", views.project_create, name="create"),
    path("my-submissions/", views.my_changes, name="my_changes"),
    path("<int:pk>/", views.project_detail, name="detail"),
    path("<int:pk>/edit/", views.project_edit, name="edit"),
    path("<int:pk>/delete/", views.project_delete, name="delete"),
    path("<int:pk>/members/add/", views.member_add, name="member_add"),
    path("<int:pk>/members/<int:member_id>/remove/", views.member_remove, name="member_remove"),
    path("<int:pk>/members/<int:member_id>/role/", views.member_role, name="member_role"),
    path("<int:pk>/changes/new/", views.change_create, name="change_create"),
    path("changes/<int:pk>/", views.change_detail, name="change_detail"),
    path("changes/<int:pk>/edit/", views.change_edit, name="change_edit"),
    path("changes/<int:pk>/delete/", views.change_delete, name="change_delete"),
    path("changes/<int:pk>/review/", views.change_review, name="change_review"),
]
