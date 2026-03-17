"""
Release workflow

Combines freeze_execute, freeze_complete, and freeze_publish
from jira-scripts into a single module.

Handles release issue state changes:
- Freeze Execute: test → release merge
- Freeze Complete: update issue statuses + delete branches
- Release Publish: release → main + tag

Key difference from jira-scripts:
- Uses Plane API instead of Jira API
- Uses Plane labels instead of Jira components for repository discovery
- Simplified: no Changelog generation, no cumulative release mode
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from app.core.config import settings
from app.services.gitlab_service import gitlab_service
from app.services.plane_service import plane_service
from app.services.module_config_service import module_config_service

from ..operations.branch import delete_story_branches
from ..operations.comment import (
    add_freeze_execute_comment,
    add_freeze_complete_comment,
    add_release_complete_comment,
)
from ..utils.extractors import (
    extract_issue_identifier,
    extract_labels,
    extract_repositories_from_issues,
    find_feature_branches,
    match_modules_by_labels,
)


logger = logging.getLogger(__name__)


# ============================================================================
# Freeze Execute: test → release merge
# ============================================================================


async def handle_freeze_execute(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute freeze: merge test → release for all repositories

    Args:
        issue_data: Release issue data from webhook

    Returns:
        Workflow result dict
    """
    issue_identifier = extract_issue_identifier(issue_data)
    issue_id = str(issue_data.get("id", ""))

    logger.info(f"[Freeze Execute] Starting for {issue_identifier}")

    # 1. Get all issues in "To Publish" state
    project_id = settings.plane_project_id
    to_publish_state_id = await plane_service.get_state_id(project_id, settings.state_to_publish)

    if not to_publish_state_id:
        logger.error("[Freeze Execute] Cannot find 'To Publish' state")
        await plane_service.add_comment(
            project_id, issue_id,
            "<p>Cannot find 'To Publish' state. Please check state configuration.</p>"
        )
        return {"status": "error", "reason": "state_not_found"}

    to_publish_issues = await plane_service.list_issues(project_id, state_id=to_publish_state_id)

    if not to_publish_issues:
        logger.warning("[Freeze Execute] No issues in 'To Publish' state")
        await plane_service.add_comment(
            project_id, issue_id,
            "<p>No issues found in 'To Publish' state.</p>"
        )
        return {"status": "skipped", "reason": "no_issues"}

    logger.info(f"[Freeze Execute] Found {len(to_publish_issues)} issues to freeze")

    # 2. Extract repositories from issues (via labels → modules)
    repositories = extract_repositories_from_issues(to_publish_issues)

    if not repositories:
        logger.warning("[Freeze Execute] No repositories found")
        await plane_service.add_comment(
            project_id, issue_id,
            "<p>No repositories found from issue labels.</p>"
        )
        return {"status": "skipped", "reason": "no_repositories"}

    # 3. Execute test → release merge for each repository
    logger.info(f"[Freeze Execute] Merging test → release for {len(repositories)} repos...")

    tasks = [
        _process_repo_freeze_merge(repo_id, issue_identifier)
        for repo_id in repositories.keys()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            repo_id = list(repositories.keys())[i]
            logger.error(f"[Freeze Execute] Error for {repo_id}: {result}")
            processed_results.append({
                "repository": repo_id, "success": False,
                "error": str(result), "mr_url": None,
            })
        else:
            processed_results.append(result)

    # 4. Record results
    version = issue_data.get("name", issue_identifier)
    processed_issues_info = [
        {"identifier": extract_issue_identifier(i), "name": i.get("name", "")}
        for i in to_publish_issues
    ]

    await add_freeze_execute_comment(
        issue_id, version, processed_issues_info, processed_results, repositories
    )

    success_count = sum(1 for r in processed_results if r["success"])
    logger.info(f"[Freeze Execute] Complete: {success_count}/{len(processed_results)} repos merged")

    return {
        "status": "completed",
        "repos_total": len(processed_results),
        "repos_success": success_count,
    }


async def _process_repo_freeze_merge(repo_id: str, freeze_identifier: str) -> Dict[str, Any]:
    """Merge test → release for a single repository"""
    module = module_config_service.get_module_by_project_id(repo_id)
    if not module:
        return {"repository": repo_id, "success": False, "error": "Module config not found", "mr_url": None}

    test_branch = module_config_service.get_test_branch(module)
    release_branch = module_config_service.get_release_branch(module)

    # Create MR: test → release
    mr = gitlab_service.create_merge_request(
        project_id=repo_id,
        source_branch=test_branch,
        target_branch=release_branch,
        title=f"[Freeze] {freeze_identifier}: merge {test_branch} to {release_branch}",
        description=f"Freeze: {freeze_identifier}\nAuto freeze merge",
    )

    if not mr:
        return {"repository": repo_id, "success": False, "error": "Failed to create MR", "mr_url": None}

    mr_iid = mr["iid"]
    mr_url = mr.get("web_url", "")

    # Merge
    merge_result = gitlab_service.merge_merge_request(
        project_id=repo_id,
        mr_identifier=mr_iid,
        merge_commit_message=f"[Freeze] {freeze_identifier}: {test_branch} → {release_branch}",
    )

    if merge_result.success:
        return {"repository": repo_id, "success": True, "mr_url": merge_result.mr_url}
    elif merge_result.status == "same_content":
        # Close MR if same content
        if merge_result.mr_iid:
            gitlab_service.close_merge_request(project_id=repo_id, mr_identifier=merge_result.mr_iid)
        return {
            "repository": repo_id, "success": False,
            "skip_reason": "same_content",
            "error": merge_result.error_message,
            "mr_url": merge_result.mr_url,
        }
    else:
        return {
            "repository": repo_id, "success": False,
            "error": merge_result.error_message,
            "mr_url": merge_result.mr_url,
        }


# ============================================================================
# Freeze Complete: update statuses + delete branches
# ============================================================================


async def handle_freeze_complete(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complete freeze: update issue statuses to Done and delete feature branches

    Args:
        issue_data: Release issue data from webhook

    Returns:
        Workflow result dict
    """
    issue_identifier = extract_issue_identifier(issue_data)
    issue_id = str(issue_data.get("id", ""))

    logger.info(f"[Freeze Complete] Starting for {issue_identifier}")

    # 1. Get all "To Publish" issues
    project_id = settings.plane_project_id
    to_publish_state_id = await plane_service.get_state_id(project_id, settings.state_to_publish)
    done_state_id = await plane_service.get_state_id(project_id, settings.state_done)

    if not to_publish_state_id or not done_state_id:
        logger.error("[Freeze Complete] Cannot find required states")
        return {"status": "error", "reason": "state_not_found"}

    to_publish_issues = await plane_service.list_issues(project_id, state_id=to_publish_state_id)

    if not to_publish_issues:
        logger.warning("[Freeze Complete] No issues to process")
        return {"status": "skipped", "reason": "no_issues"}

    # 2. Process each issue
    tasks = [
        _process_single_issue_complete(issue, done_state_id, issue_identifier)
        for issue in to_publish_issues
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    issue_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            issue = to_publish_issues[i]
            logger.error(f"[Freeze Complete] Error: {result}")
            issue_results.append({
                "issue_identifier": extract_issue_identifier(issue),
                "summary": issue.get("name", ""),
                "success": False,
                "error": str(result),
            })
        else:
            issue_results.append(result)

    # 3. Record results
    version = issue_data.get("name", issue_identifier)
    await add_freeze_complete_comment(issue_id, version, issue_results)

    success_count = sum(1 for r in issue_results if r["success"])
    logger.info(f"[Freeze Complete] Done: {success_count}/{len(issue_results)} issues processed")

    return {
        "status": "completed",
        "issues_total": len(issue_results),
        "issues_success": success_count,
    }


async def _process_single_issue_complete(
    issue: Dict[str, Any], done_state_id: str, freeze_identifier: str
) -> Dict[str, Any]:
    """Process a single issue: update state to Done + delete branches"""
    issue_id = str(issue.get("id", ""))
    issue_identifier = extract_issue_identifier(issue)
    summary = issue.get("name", "")
    project_id = settings.plane_project_id

    try:
        # Update state to Done
        updated = await plane_service.update_issue_state(project_id, issue_id, done_state_id)
        if not updated:
            return {
                "issue_identifier": issue_identifier,
                "summary": summary,
                "success": False,
                "status_updated": False,
                "branches_total": 0,
                "branches_deleted": 0,
                "branches_failed": 0,
                "error": "State update failed",
            }

        # Find and delete branches
        labels = extract_labels(issue)
        modules = match_modules_by_labels(labels)
        branches = await find_feature_branches(issue_identifier, modules) if modules else {}

        if not branches:
            return {
                "issue_identifier": issue_identifier,
                "summary": summary,
                "success": True,
                "status_updated": True,
                "branches_total": 0,
                "branches_deleted": 0,
                "branches_failed": 0,
                "error": None,
            }

        delete_results = await delete_story_branches(issue_identifier, branches)

        total = len(delete_results)
        deleted = sum(1 for r in delete_results if r["success"])

        return {
            "issue_identifier": issue_identifier,
            "summary": summary,
            "success": True,
            "status_updated": True,
            "branches_total": total,
            "branches_deleted": deleted,
            "branches_failed": total - deleted,
            "error": None,
        }

    except Exception as e:
        logger.error(f"[Freeze Complete] Error processing {issue_identifier}: {e}")
        return {
            "issue_identifier": issue_identifier,
            "summary": summary,
            "success": False,
            "status_updated": False,
            "branches_total": 0,
            "branches_deleted": 0,
            "branches_failed": 0,
            "error": str(e),
        }


# ============================================================================
# Release Publish: release → main + tag
# ============================================================================


async def handle_release_publish(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publish release: merge release → main and create tags

    Args:
        issue_data: Release issue data from webhook

    Returns:
        Workflow result dict
    """
    issue_identifier = extract_issue_identifier(issue_data)
    issue_id = str(issue_data.get("id", ""))
    version = issue_data.get("name", issue_identifier)

    logger.info(f"[Release] Starting release publish for {issue_identifier}, version: {version}")

    # 1. Get repositories (from labels of "To Publish" issues, same as freeze)
    project_id = settings.plane_project_id

    # Get all "Done" issues that were part of this release (recently moved to Done)
    done_state_id = await plane_service.get_state_id(project_id, settings.state_done)
    if not done_state_id:
        logger.error("[Release] Cannot find 'Done' state")
        return {"status": "error", "reason": "state_not_found"}

    # Get repositories from the release issue labels
    labels = extract_labels(issue_data)
    modules = match_modules_by_labels(labels)

    if not modules:
        # Fallback: get repos from all modules
        modules = module_config_service.get_all_modules()

    repo_ids = [m.gitlab.project_id for m in modules]

    if not repo_ids:
        logger.warning("[Release] No repositories found")
        await plane_service.add_comment(
            project_id, issue_id,
            "<p>No repositories found for release.</p>"
        )
        return {"status": "skipped", "reason": "no_repositories"}

    # 2. Execute release → main + tag for each repo
    logger.info(f"[Release] Publishing {len(repo_ids)} repos...")

    tasks = [
        _process_repo_release(repo_id, version, issue_identifier)
        for repo_id in repo_ids
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"[Release] Error for {repo_ids[i]}: {result}")
            processed_results.append({
                "success": False, "repo_id": repo_ids[i], "error": str(result),
            })
        else:
            processed_results.append(result)

    # 3. Record results
    await add_release_complete_comment(issue_id, version, processed_results)

    success_count = sum(1 for r in processed_results if r["success"])
    logger.info(f"[Release] Complete: {success_count}/{len(processed_results)} repos released")

    return {
        "status": "completed",
        "repos_total": len(processed_results),
        "repos_success": success_count,
    }


async def _process_repo_release(repo_id: str, version: str, release_identifier: str) -> Dict[str, Any]:
    """Release a single repository: release → main + tag"""
    module = module_config_service.get_module_by_project_id(repo_id)
    if not module:
        return {"success": False, "repo_id": repo_id, "error": "Module config not found"}

    release_branch = module_config_service.get_release_branch(module)
    main_branch = module.gitlab.branches.get("main", "main")

    # Create MR: release → main
    mr = gitlab_service.create_merge_request(
        project_id=repo_id,
        source_branch=release_branch,
        target_branch=main_branch,
        title=f"[Release] v{version}: merge {release_branch} to {main_branch}",
        description=f"Release: v{version}\n{release_identifier}",
    )

    mr_url = ""
    if mr:
        mr_iid = mr["iid"]
        merge_result = gitlab_service.merge_merge_request(
            project_id=repo_id,
            mr_identifier=mr_iid,
            merge_commit_message=f"[Release] v{version}: {release_branch} → {main_branch}",
        )

        if not merge_result.success and merge_result.status != "same_content":
            return {
                "success": False,
                "repo_id": repo_id,
                "error": merge_result.error_message,
                "mr_url": merge_result.mr_url,
            }

        mr_url = merge_result.mr_url or ""

        # Close MR if same content
        if merge_result.status == "same_content" and merge_result.mr_iid:
            gitlab_service.close_merge_request(project_id=repo_id, mr_identifier=merge_result.mr_iid)

    # Create tag
    tag_result = {"success": False, "tag_url": None, "error": None}
    try:
        tag = gitlab_service.create_tag(
            project_id=repo_id,
            tag_name=f"v{version}",
            ref=main_branch,
            message=f"Release v{version}",
        )
        if tag:
            tag_url = gitlab_service.get_tag_url(repo_id, f"v{version}")
            tag_result = {"success": True, "tag_url": tag_url, "error": None}
            logger.info(f"[Release] Created tag v{version} for {repo_id}")
        else:
            tag_result = {"success": False, "tag_url": None, "error": "Tag creation failed"}
    except Exception as e:
        tag_result = {"success": False, "tag_url": None, "error": str(e)}

    return {
        "success": True,
        "repo_id": repo_id,
        "mr_url": mr_url,
        "tag": tag_result,
    }
