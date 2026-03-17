"""
Test passed workflow (Testing → To Publish)

Handles issue state change to To Publish.
No Git operations, only records test passed information.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from app.core.config import settings
from app.services.plane_service import plane_service

from ..utils.extractors import extract_issue_identifier


logger = logging.getLogger(__name__)


async def handle_to_publish(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Test passed: record to publish queue

    No Git operations, only records test passed status.

    Args:
        issue_data: Plane issue data from webhook

    Returns:
        Workflow result dict
    """
    issue_identifier = extract_issue_identifier(issue_data)
    issue_id = str(issue_data.get("id", ""))

    logger.info(f"[Test Passed] Issue {issue_identifier} entering publish queue")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    comment_html = f"""<h3 style="color:#10b981;">Test Passed</h3>
<div style="background:#f0fff4;border:1px solid #10b981;padding:12px;border-radius:4px;">
<p><strong>Time:</strong> {current_time}</p>
<p>Issue has passed testing and is now in the publish queue, waiting for release freeze.</p>
</div>"""

    project_id = settings.plane_project_id
    result = await plane_service.add_comment(project_id, issue_id, comment_html)

    if result:
        logger.info(f"[Test Passed] Recorded for {issue_identifier}")
    else:
        logger.error(f"[Test Passed] Failed to record for {issue_identifier}")

    return {"status": "completed", "issue_identifier": issue_identifier}
