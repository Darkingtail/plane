"""
Merge operations module

Provides generic merge logic for feature branches to target branches (dev/test).

Key difference from jira-scripts:
- Branch discovery uses GitLab API search (not Jira comment parsing)
"""

import logging
from typing import Any

from app.services.gitlab_service import gitlab_service
from app.services.module_config_service import module_config_service

from ..utils.extractors import find_feature_branches, match_modules_by_labels, extract_labels, extract_issue_identifier
from .types import MergeResultItem, MergeResultList


logger = logging.getLogger(__name__)


async def merge_feature_to_branch(
    issue_identifier: str, issue_data: dict, target_branch_type: str, workflow_name: str
) -> MergeResultList:
    """
    Generic feature → target_branch merge workflow

    Args:
        issue_identifier: Issue identifier (e.g., 'PROJ-123')
        issue_data: Plane issue data (used to extract labels → modules)
        target_branch_type: Target branch type ("dev" or "test")
        workflow_name: Workflow name for logging and MR title

    Returns:
        MergeResultList: List of merge results
    """
    logger.info(f"[{workflow_name}] Starting workflow for issue {issue_identifier}")

    # 1. Extract labels and match modules
    labels = extract_labels(issue_data)
    modules = match_modules_by_labels(labels)

    if not modules:
        logger.warning(f"[{workflow_name}] Issue {issue_identifier} has no matching modules")
        return []

    # 2. Find feature branches via GitLab API search
    branches = await find_feature_branches(issue_identifier, modules)

    if not branches:
        logger.warning(f"[{workflow_name}] No feature branches found for {issue_identifier}")
        return []

    # 3. Execute merge for each module
    results = []

    for module_name, branch_name in branches.items():
        result = await process_single_module_merge(
            issue_identifier=issue_identifier,
            module_name=module_name,
            branch_name=branch_name,
            target_branch_type=target_branch_type,
            workflow_name=workflow_name,
        )
        results.append(result)

    logger.info(f"[{workflow_name}] Issue {issue_identifier} workflow completed")
    return results


async def process_single_module_merge(
    issue_identifier: str,
    module_name: str,
    branch_name: str,
    target_branch_type: str,
    workflow_name: str,
) -> MergeResultItem:
    """
    Process merge for a single module

    Args:
        issue_identifier: Issue identifier
        module_name: Module name
        branch_name: Feature branch name
        target_branch_type: Target branch type ("dev" or "test")
        workflow_name: Workflow name

    Returns:
        MergeResultItem: Merge result
    """
    # Get module config
    module = module_config_service.get_module(module_name)
    if not module:
        logger.error(f"[{workflow_name}] Module {module_name} config not found")
        return {"module": module_name, "success": False, "error": "Module config not found"}

    project_id = module.gitlab.project_id

    # Get target branch name (supports custom branch names)
    if target_branch_type == "dev":
        target_branch = module_config_service.get_dev_branch(module)
    elif target_branch_type == "test":
        target_branch = module_config_service.get_test_branch(module)
    else:
        logger.error(f"[{workflow_name}] Unsupported branch type: {target_branch_type}")
        return {
            "module": module_name,
            "success": False,
            "error": f"Unsupported branch type: {target_branch_type}",
        }

    logger.info(f"[{workflow_name}] Processing {module_name}: {branch_name} → {target_branch}")

    # Create Merge Request
    mr = gitlab_service.create_merge_request(
        project_id=project_id,
        source_branch=branch_name,
        target_branch=target_branch,
        title=f"[{workflow_name}] {issue_identifier}: merge {branch_name} to {target_branch}",
        description=f"Issue: {issue_identifier}\nAuto {workflow_name} merge",
    )

    if not mr:
        logger.error(f"[{workflow_name}] Failed to create MR: {module_name}")
        return {"module": module_name, "success": False, "error": "Failed to create MR"}

    mr_iid = mr["iid"]

    # Attempt to merge MR
    merge_result = gitlab_service.merge_merge_request(
        project_id=project_id,
        mr_identifier=mr_iid,
        merge_commit_message=f"[{workflow_name}] {issue_identifier}: {branch_name} → {target_branch}",
    )

    # Handle merge result
    return handle_merge_result(
        merge_result=merge_result,
        module_name=module_name,
        branch_name=branch_name,
        project_id=project_id,
        target_branch=target_branch,
        workflow_name=workflow_name,
    )


def handle_merge_result(
    merge_result: Any,
    module_name: str,
    branch_name: str,
    project_id: str,
    target_branch: str,
    workflow_name: str,
) -> MergeResultItem:
    """
    Handle merge result (success/conflict/no-merge-needed/other errors)
    """
    if merge_result.success:
        logger.info(f"[{workflow_name}] Merge success: {module_name}, commit: {merge_result.merge_commit_sha}")
        return {
            "module": module_name,
            "branch_name": branch_name,
            "success": True,
            "commit_sha": merge_result.merge_commit_sha,
            "mr_url": merge_result.mr_url,
            "target_branch": target_branch,
        }

    elif merge_result.status == "same_content":
        logger.info(f"[{workflow_name}] No merge needed: {module_name} (same content)")

        mr_closed = False
        if merge_result.mr_iid:
            close_success = gitlab_service.close_merge_request(
                project_id=project_id, mr_identifier=merge_result.mr_iid
            )
            if close_success:
                logger.info(f"[{workflow_name}] Auto-closed MR #{merge_result.mr_iid}: {module_name}")
                mr_closed = True

        return {
            "module": module_name,
            "branch_name": branch_name,
            "success": False,
            "error": f"No merge needed: {merge_result.error_message}",
            "mr_url": merge_result.mr_url,
            "target_branch": target_branch,
            "skip_reason": "same_content",
            "mr_closed": mr_closed,
        }

    elif merge_result.status == "conflict":
        logger.warning(f"[{workflow_name}] Merge conflict: {module_name}")
        return {
            "module": module_name,
            "branch_name": branch_name,
            "success": False,
            "error": f"Conflict: {merge_result.error_message}",
            "mr_url": merge_result.mr_url,
            "status": "conflict",
        }

    elif merge_result.status == "already_merged":
        if merge_result.mr_state == "merged":
            logger.info(f"[{workflow_name}] Already merged: {module_name}")
            return {
                "module": module_name,
                "branch_name": branch_name,
                "success": True,
                "commit_sha": merge_result.merge_commit_sha,
                "mr_url": merge_result.mr_url,
                "target_branch": target_branch,
            }
        else:
            logger.warning(f"[{workflow_name}] MR closed: {module_name}, state={merge_result.mr_state}")
            return {
                "module": module_name,
                "branch_name": branch_name,
                "success": False,
                "error": f"MR closed ({merge_result.mr_state})",
                "mr_url": merge_result.mr_url,
                "target_branch": target_branch,
            }

    else:
        logger.error(f"[{workflow_name}] Merge failed: {module_name}, {merge_result.error_message}")
        return {
            "module": module_name,
            "branch_name": branch_name,
            "success": False,
            "error": merge_result.error_message,
            "mr_url": merge_result.mr_url,
            "target_branch": target_branch,
        }
