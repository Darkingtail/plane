"""
Testing workflow (→ Testing state)

Handles issue state change to Testing.
Executes feature → test merge.

Key difference from jira-scripts:
- No Jpom build trigger
- No QA notification (Plane version doesn't use notification service)
- Branch discovery via GitLab API search
"""

import logging
from typing import Any, Dict

from app.core.config import settings
from app.services.plane_service import plane_service

from ..operations.comment import add_merge_comment, notify_conflict
from ..operations.merge import merge_feature_to_branch
from ..operations.types import MergeResultItem
from ..utils.extractors import extract_issue_identifier


logger = logging.getLogger(__name__)


async def handle_testing(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Testing workflow: feature → test merge

    Args:
        issue_data: Plane issue data from webhook

    Returns:
        Workflow result dict
    """
    issue_identifier = extract_issue_identifier(issue_data)
    issue_id = str(issue_data.get("id", ""))

    logger.info(f"[Testing] Starting workflow for issue {issue_identifier}")

    # 1. Execute merge workflow
    results = await merge_feature_to_branch(
        issue_identifier=issue_identifier,
        issue_data=issue_data,
        target_branch_type="test",
        workflow_name="Testing",
    )

    # 2. Handle no branches found
    if not results:
        logger.warning(f"[Testing] Issue {issue_identifier} has no feature branches")
        project_id = settings.plane_project_id
        await plane_service.add_comment(
            project_id, issue_id,
            "<p>No feature branches found. Cannot auto-merge to test.</p>"
        )
        return {"status": "no_branches", "issue_identifier": issue_identifier}

    # 3. Send conflict notifications
    conflict_results = [r for r in results if r.get("status") == "conflict"]
    for r in conflict_results:
        await notify_conflict(
            issue_id=issue_id,
            module_name=r["module"],
            branch_name=_extract_branch_name(r),
            target_branch=r.get("target_branch", "test"),
            mr_url=r.get("mr_url", ""),
            reason="has_conflicts",
        )

    # 4. Record merge results
    success_count = sum(1 for r in results if r.get("success"))
    skip_count = sum(1 for r in results if r.get("skip_reason") == "same_content")

    if success_count > 0 or skip_count > 0:
        actual_target = results[0].get("target_branch", "test") if results else "test"
        await add_merge_comment(issue_id, actual_target, results)

    logger.info(f"[Testing] Issue {issue_identifier} workflow completed")

    return {
        "status": "completed",
        "issue_identifier": issue_identifier,
        "success": success_count,
        "skipped": skip_count,
        "failed": len(results) - success_count - skip_count,
    }


def _extract_branch_name(result: MergeResultItem) -> str:
    """Extract branch name from merge result"""
    return result.get("branch_name", "feature branch")
