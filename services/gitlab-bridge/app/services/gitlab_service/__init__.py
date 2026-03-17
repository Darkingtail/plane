"""
GitLab Service - 统一入口

提供向后兼容的 API,同时支持模块化访问方式
"""

from typing import Any, Dict, Optional

from .base import GitLabServiceBase
from .branch_operations import BranchOperations
from .merge_request_operations import MergeRequestOperations
from .models import MergeResult
from .project_operations import ProjectOperations
from .tag_operations import TagOperations


__all__ = [
    "GitLabService",
    "gitlab_service",
    "MergeResult",
]


class GitLabService(GitLabServiceBase):
    """
    GitLab Service 主类

    组合各个功能模块,提供统一的服务入口
    """

    def __init__(self):
        super().__init__()
        self.project = ProjectOperations(self)
        self.branches = BranchOperations(self)
        self.merge_requests = MergeRequestOperations(self)
        self.tags = TagOperations(self)

    # 向后兼容 - 项目和用户操作
    def get_user(self) -> Optional[Dict[str, Any]]:
        return self.project.get_user()

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.project.get_project(project_id)

    # 向后兼容 - 分支操作
    def list_branches(self, project_id: str, search: Optional[str] = None) -> list:
        return self.branches.list_branches(project_id, search)

    def branch_exists(self, project_id: str, branch_name: str) -> bool:
        return self.branches.branch_exists(project_id, branch_name)

    def create_branch(self, project_id: str, branch_name: str, ref: str) -> Optional[Dict[str, Any]]:
        return self.branches.create_branch(project_id, branch_name, ref)

    def delete_branch(self, project_id: str, branch_name: str) -> bool:
        return self.branches.delete_branch(project_id, branch_name)

    def create_branch_for_module(self, module, branch_name: str, story_key: str) -> Optional[Dict[str, Any]]:
        return self.branches.create_branch_for_module(module, branch_name, story_key)

    def get_branch_url(self, project_id: str, branch_name: str) -> str:
        return self.branches.get_branch_url(project_id, branch_name)

    # 向后兼容 - Merge Request 操作
    def create_merge_request(
        self,
        project_id: str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: Optional[str] = None,
        remove_source_branch: bool = False,
    ) -> Optional[Dict[str, Any]]:
        return self.merge_requests.create_merge_request(
            project_id, source_branch, target_branch, title, description, remove_source_branch
        )

    def get_merge_request(self, project_id: str, mr_identifier: int, use_iid: bool = True) -> Optional[Dict[str, Any]]:
        return self.merge_requests.get_merge_request(project_id, mr_identifier, use_iid)

    def can_merge(self, project_id: str, mr_identifier: int) -> tuple[bool, Optional[str]]:
        return self.merge_requests.can_merge(project_id, mr_identifier)

    def merge_merge_request(
        self,
        project_id: str,
        mr_identifier: int,
        merge_commit_message: Optional[str] = None,
        should_remove_source_branch: bool = False,
        use_iid: bool = True,
    ) -> MergeResult:
        return self.merge_requests.merge_merge_request(
            project_id, mr_identifier, merge_commit_message, should_remove_source_branch, use_iid
        )

    def get_merge_request_url(self, project_id: str, mr_iid: int) -> str:
        return self.merge_requests.get_merge_request_url(project_id, mr_iid)

    def close_merge_request(
        self, project_id: str, mr_identifier: int, state_event: str = "close", use_iid: bool = True
    ) -> bool:
        return self.merge_requests.close_merge_request(project_id, mr_identifier, state_event, use_iid)

    # 向后兼容 - Tag 操作
    def create_tag(
        self, project_id: str, tag_name: str, ref: str, message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        return self.tags.create_tag(project_id, tag_name, ref, message)

    def get_tag(self, project_id: str, tag_name: str) -> Optional[Dict[str, Any]]:
        return self.tags.get_tag(project_id, tag_name)

    def get_tag_url(self, project_id: str, tag_name: str) -> str:
        return self.tags.get_tag_url(project_id, tag_name)


# Global service instance
gitlab_service = GitLabService()
