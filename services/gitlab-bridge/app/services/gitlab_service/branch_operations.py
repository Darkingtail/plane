"""
GitLab Service 分支操作模块
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import quote

import requests


if TYPE_CHECKING:
    from .base import GitLabServiceBase

from app.services.module_config_service import ModuleConfig, module_config_service


logger = logging.getLogger(__name__)


class BranchOperations:
    """GitLab 分支操作"""

    def __init__(self, base: "GitLabServiceBase"):
        self.base = base

    def list_branches(self, project_id: str, search: Optional[str] = None) -> list:
        try:
            project_id_encoded = project_id.replace("/", "%2F")
            params = {}
            if search:
                params["search"] = search
            response = self.base.session.get(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/branches"),
                headers=self.base._get_headers(),
                params=params,
                timeout=self.base._get_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list branches for {project_id}: {e}")
            return []

    def branch_exists(self, project_id: str, branch_name: str) -> bool:
        try:
            project_id_encoded = project_id.replace("/", "%2F")
            branch_name_encoded = branch_name.replace("/", "%2F")
            response = self.base.session.get(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/branches/{branch_name_encoded}"),
                headers=self.base._get_headers(),
                timeout=self.base._get_timeout(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to check branch existence: {e}")
            return False

    def search_story_branches(self, project_id: str, issue_identifier: str) -> list:
        """
        搜索某个 Issue 的所有 feature 分支

        Args:
            project_id: GitLab project ID or namespace/project path
            issue_identifier: Plane Issue identifier (如 PROJ-123)
        """
        try:
            branches = self.list_branches(project_id, search=issue_identifier)
            prefix = f"feature/{issue_identifier}_"
            story_branches = [branch for branch in branches if branch.get("name", "").startswith(prefix)]
            if story_branches:
                logger.info(
                    f"Found {len(story_branches)} existing branch(es) for issue {issue_identifier} "
                    f"in {project_id}: {[b['name'] for b in story_branches]}"
                )
            else:
                logger.debug(f"No existing branches found for issue {issue_identifier} in {project_id}")
            return story_branches
        except Exception as e:
            logger.error(f"Failed to search story branches for {issue_identifier} in {project_id}: {e}")
            return []

    def get_first_story_branch(self, project_id: str, issue_identifier: str) -> Optional[str]:
        branches = self.search_story_branches(project_id, issue_identifier)
        if branches:
            return branches[0].get("name")
        return None

    def create_branch(self, project_id: str, branch_name: str, ref: str) -> Optional[Dict[str, Any]]:
        try:
            project_id_encoded = project_id.replace("/", "%2F")
            if self.base.api_version == "v3":
                data = {"branch_name": branch_name, "ref": ref}
            else:
                data = {"branch": branch_name, "ref": ref}
            response = self.base.session.post(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/branches"),
                headers=self.base._get_headers(),
                json=data,
                timeout=self.base._get_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_detail = "Unknown error"
            try:
                error_json = e.response.json()
                error_detail = error_json.get("message") or error_json.get("error") or str(error_json)
            except Exception:
                error_detail = e.response.text[:200] if e.response.text else str(e)
            logger.error(
                f"Failed to create branch {branch_name} in {project_id}: HTTP {e.response.status_code} - {error_detail}"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to create branch {branch_name} in {project_id}: {e}")
            return None

    def delete_branch(self, project_id: str, branch_name: str) -> bool:
        try:
            project_id_encoded = project_id.replace("/", "%2F")
            branch_name_encoded = branch_name.replace("/", "%2F")
            response = self.base.session.delete(
                self.base._get_api_url(f"projects/{project_id_encoded}/repository/branches/{branch_name_encoded}"),
                headers=self.base._get_headers(),
                timeout=self.base._get_timeout(),
            )
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.info(f"Branch {branch_name} does not exist (already deleted) in {project_id}")
                return True
            else:
                logger.error(f"Failed to delete branch {branch_name} in {project_id}: HTTP {e.response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete branch {branch_name} in {project_id}: {e}")
            return False

    def create_branch_for_module(
        self, module: ModuleConfig, branch_name: str, issue_identifier: str
    ) -> Optional[Dict[str, Any]]:
        config = module_config_service.config
        if config.branch_creation.check_existence:
            existing_branch = self.get_first_story_branch(module.gitlab.project_id, issue_identifier)
            if existing_branch:
                logger.info(f"Issue {issue_identifier} already has branch '{existing_branch}' in {module.gitlab.project_id}")
                if config.branch_creation.if_exists == "skip":
                    return {
                        "name": existing_branch,
                        "exists": True,
                        "skipped": True,
                        "created": False,
                        "message": f"Branch already exists for issue {issue_identifier}",
                    }
                elif config.branch_creation.if_exists == "overwrite":
                    self.delete_branch(module.gitlab.project_id, existing_branch)
                elif config.branch_creation.if_exists == "error":
                    raise Exception(f"Issue {issue_identifier} already has branch '{existing_branch}'")

        release_branch = module_config_service.get_release_branch(module)
        logger.info(f"Creating branch {branch_name} in {module.gitlab.project_id} from {release_branch}")
        created = self.create_branch(project_id=module.gitlab.project_id, branch_name=branch_name, ref=release_branch)
        if created:
            created["created"] = True
            created["skipped"] = False
            created["exists"] = False
        return created

    def get_branch_url(self, project_id: str, branch_name: str) -> str:
        branch_name_encoded = quote(branch_name, safe="")
        gitlab_url = module_config_service.get_gitlab_url()
        if self.base.api_version == "v3":
            return f"{gitlab_url}/{project_id}/tree/{branch_name_encoded}"
        else:
            return f"{gitlab_url}/{project_id}/-/tree/{branch_name_encoded}"
