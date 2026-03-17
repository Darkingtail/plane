"""
Branch operations module

Provides feature branch creation and deletion.

Key difference from jira-scripts:
- Uses plane_service.add_comment() instead of jira_service.add_comment()
- Comment format is HTML instead of Confluence markup
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.gitlab_service import gitlab_service
from app.services.plane_service import plane_service
from app.services.module_config_service import module_config_service
from app.core.config import settings


logger = logging.getLogger(__name__)


async def delete_story_branches(issue_identifier: str, branches: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Delete all feature branches for an issue

    Args:
        issue_identifier: Issue identifier (e.g., 'PROJ-123')
        branches: Dict[module_name, branch_name]

    Returns:
        List of deletion results
    """
    results = []

    if not branches:
        logger.info(f"[Freeze Complete] Issue {issue_identifier} has no associated branches")
        return results

    for module_name, branch_name in branches.items():
        module = module_config_service.get_module(module_name)
        if not module:
            logger.warning(f"[Freeze Complete] Module {module_name} config not found")
            results.append({
                "module": module_name,
                "project_id": None,
                "branch": branch_name,
                "success": False,
                "error": "Module config not found",
            })
            continue

        project_id = module.gitlab.project_id

        try:
            success = gitlab_service.delete_branch(project_id, branch_name)
            if success:
                logger.info(f"[Freeze Complete] Deleted branch: {project_id} / {branch_name}")
                results.append({
                    "module": module_name,
                    "project_id": project_id,
                    "branch": branch_name,
                    "success": True,
                    "error": None,
                })
            else:
                logger.warning(f"[Freeze Complete] Failed to delete branch: {project_id} / {branch_name}")
                results.append({
                    "module": module_name,
                    "project_id": project_id,
                    "branch": branch_name,
                    "success": False,
                    "error": "Delete failed",
                })
        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg or "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                logger.info(f"[Freeze Complete] Branch not found (treated as deleted): {project_id} / {branch_name}")
                results.append({
                    "module": module_name,
                    "project_id": project_id,
                    "branch": branch_name,
                    "success": True,
                    "error": "Branch not found (treated as deleted)",
                })
            else:
                logger.error(f"[Freeze Complete] Error deleting branch: {project_id} / {branch_name}: {e}")
                results.append({
                    "module": module_name,
                    "project_id": project_id,
                    "branch": branch_name,
                    "success": False,
                    "error": error_msg,
                })

    return results


async def create_branch_for_module(
    module_name: str,
    branch_name: str,
    issue_identifier: str,
    issue_id: str,
    add_plane_comment: bool = True,
) -> Dict[str, Any]:
    """
    Create a GitLab branch for a single module and add a Plane comment

    Args:
        module_name: Module name
        branch_name: Branch name
        issue_identifier: Issue identifier (e.g., 'PROJ-123')
        issue_id: Plane issue UUID (for adding comments)
        add_plane_comment: Whether to add a Plane comment

    Returns:
        Branch creation result dict
    """
    result = {
        "module": module_name,
        "project_id": None,
        "branch_name": branch_name,
        "success": False,
        "skipped": False,
        "error": None,
        "comment_added": False,
    }

    try:
        # 1. Get module config
        module = module_config_service.get_module(module_name)
        if not module:
            error_msg = f"Module {module_name} config not found"
            logger.warning(f"  {error_msg}")
            result["error"] = error_msg
            if add_plane_comment and module_config_service.should_add_plane_comment():
                await _add_failure_comment(issue_id, module_name, branch_name, None, error_msg)
                result["comment_added"] = True
            return result

        result["project_id"] = module.gitlab.project_id

        # 2. Create GitLab branch
        logger.info(f"Creating branch in {module_name} ({module.gitlab.project_id})...")

        created_branch = gitlab_service.create_branch_for_module(
            module=module, branch_name=branch_name, story_key=issue_identifier
        )

        if not created_branch:
            error_msg = "Branch creation returned None"
            logger.warning(f"  {error_msg}")
            result["error"] = error_msg
            if add_plane_comment and module_config_service.should_add_plane_comment():
                await _add_failure_comment(
                    issue_id, module_name, branch_name, module.gitlab.project_id, error_msg
                )
                result["comment_added"] = True
            return result

        # 3. Check if created or already existed
        if created_branch.get("skipped"):
            result["skipped"] = True
            result["success"] = True
            result["branch_name"] = created_branch.get("name")
            logger.info(f"Branch already exists for {issue_identifier} in {module_name}: {created_branch.get('name')}")
            return result
        else:
            result["success"] = True
            logger.info(f"Successfully created branch in {module_name}")

        # 4. Add Plane comment (only for newly created branches)
        if add_plane_comment and module_config_service.should_add_plane_comment():
            try:
                from .comment import format_branch_creation_comment

                actual_branch_name = result["branch_name"]
                branch_url = gitlab_service.get_branch_url(module.gitlab.project_id, actual_branch_name)
                base_branch = module_config_service.get_release_branch(module)

                comment_html = format_branch_creation_comment(
                    module=module,
                    branch_name=actual_branch_name,
                    branch_url=branch_url,
                    base_branch=base_branch,
                )

                project_id = settings.plane_project_id
                comment_result = await plane_service.add_comment(project_id, issue_id, comment_html)

                if comment_result:
                    result["comment_added"] = True
                    logger.info(f"Added comment for {module_name}")
                else:
                    logger.warning(f"Failed to add comment for {module_name}")

            except Exception as comment_error:
                logger.error(f"Error adding comment for {module_name}: {comment_error}")

        return result

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating branch in {module_name}: {error_msg}")
        result["error"] = error_msg
        if add_plane_comment and module_config_service.should_add_plane_comment():
            try:
                await _add_failure_comment(
                    issue_id, module_name, branch_name, result.get("project_id"), error_msg
                )
                result["comment_added"] = True
            except Exception as comment_error:
                logger.error(f"Error adding failure comment: {comment_error}")
        return result


async def _add_failure_comment(
    issue_id: str, module_name: str, branch_name: str, project_id: Optional[str], error: str
):
    """Add branch creation failure comment (internal helper)"""
    from .comment import format_branch_creation_failure_comment

    comment_html = format_branch_creation_failure_comment(
        module_name=module_name, branch_name=branch_name, project_id=project_id, error=error
    )
    await plane_service.add_comment(settings.plane_project_id, issue_id, comment_html)
