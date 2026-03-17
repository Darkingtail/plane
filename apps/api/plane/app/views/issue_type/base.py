from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import WorkSpaceAdminPermission, allow_permission, ROLE
from plane.app.serializers import IssueTypeSerializer, ProjectIssueTypeSerializer
from plane.db.models import IssueType, ProjectIssueType, Workspace
from ..base import BaseViewSet, BaseAPIView


class WorkspaceIssueTypeViewSet(BaseViewSet):
    """工作区级 Issue Type CRUD"""
    serializer_class = IssueTypeSerializer
    model = IssueType

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(workspace__slug=self.kwargs.get("slug"))
            .order_by("level", "name")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug):
        issue_types = self.get_queryset()
        serializer = IssueTypeSerializer(issue_types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = IssueTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(workspace=workspace)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def partial_update(self, request, slug, pk):
        issue_type = IssueType.objects.get(pk=pk, workspace__slug=slug)
        serializer = IssueTypeSerializer(issue_type, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, pk):
        issue_type = IssueType.objects.get(pk=pk, workspace__slug=slug)
        if issue_type.is_default:
            return Response(
                {"error": "Cannot delete the default issue type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        issue_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectIssueTypeViewSet(BaseViewSet):
    """项目级 Issue Type 配置"""
    serializer_class = ProjectIssueTypeSerializer
    model = ProjectIssueType

    def get_queryset(self):
        return (
            self.filter_queryset(super().get_queryset())
            .filter(
                workspace__slug=self.kwargs.get("slug"),
                project_id=self.kwargs.get("project_id"),
            )
            .select_related("issue_type")
            .order_by("level")
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def list(self, request, slug, project_id):
        project_issue_types = self.get_queryset()
        serializer = ProjectIssueTypeSerializer(project_issue_types, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def create(self, request, slug, project_id):
        serializer = ProjectIssueTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project_id=project_id)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @allow_permission([ROLE.ADMIN])
    def destroy(self, request, slug, project_id, pk):
        ProjectIssueType.objects.get(pk=pk, project_id=project_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
