"""
GitLab Tag 操作模块
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

import requests


if TYPE_CHECKING:
    from .base import GitLabServiceBase

logger = logging.getLogger(__name__)


class TagOperations:
    """GitLab Tag 操作类"""

    def __init__(self, base: "GitLabServiceBase"):
        """
        初始化 Tag Operations

        Args:
            base: GitLabServiceBase 实例
        """
        self.base = base

    def create_tag(
        self, project_id: str, tag_name: str, ref: str, message: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        创建 Git tag

        GitLab API:
            POST /api/v4/projects/:id/repository/tags

        Args:
            project_id: 项目 ID 或命名空间/项目路径
            tag_name: Tag 名称（例如: v1.0.1_20251030_release）
            ref: Tag 指向的分支或 commit SHA（例如: main）
            message: Tag 注释（可选）

        Returns:
            Dict[str, Any]: Tag 数据，失败返回 None
            {
                "name": "v1.0.1_20251030_release",
                "message": "Release v1.0.1",
                "target": "2695effb5807a22ff3d138d593fd856244e155e7",
                "commit": {
                    "id": "2695effb5807a22ff3d138d593fd856244e155e7",
                    "short_id": "2695effb",
                    "title": "Initial commit",
                    "created_at": "2017-07-26T11:08:53.000+02:00",
                    "parent_ids": [],
                    "message": "Initial commit",
                    "author_name": "Example User",
                    "author_email": "user@example.com",
                    "authored_date": "2017-07-26T11:08:53.000+02:00",
                    "committer_name": "Example User",
                    "committer_email": "user@example.com",
                    "committed_date": "2017-07-26T11:08:53.000+02:00"
                },
                "release": null,
                "protected": false
            }
        """
        logger.info(f"Creating tag '{tag_name}' for project {project_id} at ref {ref}")

        try:
            project_id_encoded = project_id.replace("/", "%2F")
            data = {"tag_name": tag_name, "ref": ref}

            if message:
                data["message"] = message

            response = self.base.session.post(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/tags"),
                headers=self.base._get_headers(),
                json=data,
                timeout=self.base._get_timeout(),
            )

            if response.status_code in [200, 201]:
                logger.info(f"Tag '{tag_name}' created successfully in project {project_id}")
                return response.json()
            else:
                logger.error(f"Failed to create tag '{tag_name}' in project {project_id}: {response.status_code}")
                return None

        except requests.exceptions.HTTPError as e:
            # 检查是否是 tag 已存在的错误
            if e.response and e.response.status_code == 400:
                error_msg = str(e).lower()
                if "already exists" in error_msg or "tag already exists" in error_msg:
                    logger.warning(f"Tag '{tag_name}' already exists in project {project_id}")
                    # Tag 已存在，尝试获取现有 tag 信息
                    return self.get_tag(project_id, tag_name)
            logger.error(f"Exception creating tag '{tag_name}': {e}")
            return None
        except Exception as e:
            logger.error(f"Exception creating tag '{tag_name}': {e}")
            return None

    def get_tag(self, project_id: str, tag_name: str) -> Optional[Dict[str, Any]]:
        """
        获取 Tag 信息

        GitLab API:
            GET /api/v4/projects/:id/repository/tags/:tag_name

        Args:
            project_id: 项目 ID 或命名空间/项目路径
            tag_name: Tag 名称

        Returns:
            Dict[str, Any]: Tag 数据，失败返回 None
        """
        logger.info(f"Getting tag '{tag_name}' for project {project_id}")

        try:
            project_id_encoded = project_id.replace("/", "%2F")
            tag_name_encoded = tag_name.replace("/", "%2F")

            response = self.base.session.get(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/tags/{tag_name_encoded}"),
                headers=self.base._get_headers(),
                timeout=self.base._get_timeout(),
            )

            if response.status_code == 200:
                logger.info(f"Tag '{tag_name}' retrieved successfully")
                return response.json()
            else:
                logger.warning(f"Tag '{tag_name}' not found in project {project_id}")
                return None

        except Exception as e:
            logger.error(f"Exception getting tag '{tag_name}': {e}")
            return None

    def list_tags(self, project_id: str, search: Optional[str] = None) -> list:
        """
        列出项目的所有 tags

        GitLab API:
            GET /api/v4/projects/:id/repository/tags

        Args:
            project_id: 项目 ID 或命名空间/项目路径
            search: 可选的搜索关键词

        Returns:
            List[Dict]: Tag 列表
        """
        logger.info(f"Listing tags for project {project_id}")

        try:
            project_id_encoded = project_id.replace("/", "%2F")
            params = {}

            if search:
                params["search"] = search

            response = self.base.session.get(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/tags"),
                headers=self.base._get_headers(),
                params=params,
                timeout=self.base._get_timeout(),
            )

            if response.status_code == 200:
                tags = response.json()
                logger.info(f"Retrieved {len(tags)} tags from project {project_id}")
                return tags
            else:
                logger.warning(f"No tags found in project {project_id}")
                return []

        except Exception as e:
            logger.error(f"Exception listing tags: {e}")
            return []

    def delete_tag(self, project_id: str, tag_name: str) -> bool:
        """
        删除 Tag

        GitLab API:
            DELETE /api/v4/projects/:id/repository/tags/:tag_name

        Args:
            project_id: 项目 ID 或命名空间/项目路径
            tag_name: Tag 名称

        Returns:
            bool: 是否成功删除
        """
        logger.info(f"Deleting tag '{tag_name}' from project {project_id}")

        try:
            project_id_encoded = project_id.replace("/", "%2F")
            tag_name_encoded = tag_name.replace("/", "%2F")

            response = self.base.session.delete(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/tags/{tag_name_encoded}"),
                headers=self.base._get_headers(),
                timeout=self.base._get_timeout(),
            )

            if response.status_code in [200, 204]:
                logger.info(f"Tag '{tag_name}' deleted successfully from project {project_id}")
                return True
            else:
                logger.error(f"Failed to delete tag '{tag_name}': {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Exception deleting tag '{tag_name}': {e}")
            return False

    def get_tag_url(self, project_id: str, tag_name: str) -> str:
        """
        生成 Tag 的 Web URL

        Args:
            project_id: 项目 ID 或命名空间/项目路径
            tag_name: Tag 名称

        Returns:
            str: Tag 的完整 Web URL

        Note:
            GitLab v3 使用 /tags/ 路径
            GitLab v4+ 使用 /-/tags/ 路径
            根据检测到的 API 版本自动选择格式
        """
        # 移除 project_id 中的特殊字符编码
        safe_project_id = project_id.replace("%2F", "/")

        # 从 base 获取 GitLab URL
        from app.services.module_config_service import module_config_service

        gitlab_url = module_config_service.get_gitlab_url()

        # 根据 API 版本选择路径格式
        if self.base.api_version == "v3":
            # GitLab v3: /project/tags/tag_name
            return f"{gitlab_url}/{safe_project_id}/tags/{tag_name}"
        else:
            # GitLab v4+: /project/-/tags/tag_name
            return f"{gitlab_url}/{safe_project_id}/-/tags/{tag_name}"
