from .base import BaseSerializer
from plane.db.models import IssueType, ProjectIssueType


class IssueTypeSerializer(BaseSerializer):
    class Meta:
        model = IssueType
        fields = [
            "id",
            "workspace_id",
            "name",
            "description",
            "logo_props",
            "is_epic",
            "is_default",
            "is_active",
            "level",
        ]
        read_only_fields = ["workspace", "id"]


class ProjectIssueTypeSerializer(BaseSerializer):
    issue_type_detail = IssueTypeSerializer(source="issue_type", read_only=True)

    class Meta:
        model = ProjectIssueType
        fields = [
            "id",
            "project_id",
            "workspace_id",
            "issue_type",
            "issue_type_detail",
            "level",
            "is_default",
        ]
        read_only_fields = ["workspace", "project", "id"]
