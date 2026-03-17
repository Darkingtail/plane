from django.urls import path
from plane.app.views import WorkspaceIssueTypeViewSet, ProjectIssueTypeViewSet

urlpatterns = [
    # 工作区级 Issue Types
    path(
        "workspaces/<str:slug>/issue-types/",
        WorkspaceIssueTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-issue-types",
    ),
    path(
        "workspaces/<str:slug>/issue-types/<uuid:pk>/",
        WorkspaceIssueTypeViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="workspace-issue-type",
    ),
    # 项目级 Issue Types
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/",
        ProjectIssueTypeViewSet.as_view({"get": "list", "post": "create"}),
        name="project-issue-types",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issue-types/<uuid:pk>/",
        ProjectIssueTypeViewSet.as_view({"delete": "destroy"}),
        name="project-issue-type",
    ),
]
