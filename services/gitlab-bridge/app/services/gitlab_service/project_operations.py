"""
GitLab Service 项目和用户操作模块

提供项目信息查询和用户信息查询功能
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional


if TYPE_CHECKING:
    from .base import GitLabServiceBase


logger = logging.getLogger(__name__)


class ProjectOperations:
    """GitLab 项目和用户操作"""

    def __init__(self, base: "GitLabServiceBase"):
        """
        初始化项目操作模块

        Args:
            base: GitLabServiceBase 实例
        """
        self.base = base

    def get_user(self) -> Optional[Dict[str, Any]]:
        """
        Get current user info

        Returns:
            Dict[str, Any]: 用户信息字典，失败返回 None
        """
        try:
            response = self.base.session.get(
                self.base._get_api_url("user"),
                headers=self.base._get_headers(),
                timeout=self.base._get_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project information

        Args:
            project_id: Project ID or namespace/project path

        Returns:
            Dict[str, Any]: 项目信息字典，失败返回 None
        """
        try:
            # URL encode project_id
            project_id_encoded = project_id.replace("/", "%2F")

            response = self.base.session.get(
                self.base._get_api_url(f"projects/{project_id_encoded}"),
                headers=self.base._get_headers(),
                timeout=self.base._get_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            return None
