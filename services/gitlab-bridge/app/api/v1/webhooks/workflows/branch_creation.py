"""
Branch creation workflow

Triggered when a new issue is created or when specific labels are added.
Creates feature branches in GitLab for all matching modules.
"""

import logging
from typing import Any, Dict

from app.core.config import settings

from ..operations.branch import create_branch_for_module
from ..utils.extractors import extract_issue_identifier, extract_labels, match_modules_by_labels
from app.services.module_config_service import module_config_service


logger = logging.getLogger(__name__)


async def handle_branch_creation(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create feature branches for all matching modules

    Args:
        issue_data: Plane issue data from webhook

    Returns:
        Workflow result dict
    """
    issue_identifier = extract_issue_identifier(issue_data)
    issue_id = str(issue_data.get("id", ""))

    logger.info(f"[Branch Creation] Starting for issue {issue_identifier}")

    # 1. Extract labels and match modules
    labels = extract_labels(issue_data)
    modules = match_modules_by_labels(labels)

    if not modules:
        logger.info(f"[Branch Creation] Issue {issue_identifier} has no matching module labels")
        return {"status": "skipped", "reason": "no matching modules"}

    # 2. Create branches for each module
    results = []
    for module in modules:
        issue_name = issue_data.get("name") or issue_data.get("title") or ""
        branch_name = module_config_service.format_branch_name(issue_identifier, issue_name)

        result = await create_branch_for_module(
            module_name=module.name,
            branch_name=branch_name,
            issue_identifier=issue_identifier,
            issue_id=issue_id,
            add_plane_comment=module_config_service.should_add_plane_comment(),
        )
        results.append(result)

    # 3. Summary
    created = sum(1 for r in results if r["success"] and not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = sum(1 for r in results if not r["success"])

    logger.info(
        f"[Branch Creation] Issue {issue_identifier}: {created} created, {skipped} skipped, {failed} failed"
    )

    return {
        "status": "completed",
        "issue_identifier": issue_identifier,
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }
