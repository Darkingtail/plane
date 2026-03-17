"""
Testing failed notification (Testing → In Progress)

Handles issue state change from Testing back to In Progress.
No Git operations, only notification and logging.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from app.core.config import settings
from app.services.plane_service import plane_service

from ..utils.extractors import extract_issue_identifier


logger = logging.getLogger(__name__)


async def handle_testing_failed(issue_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Testing failed: notify developer to fix

    Triggered when issue moves from Testing back to In Progress.
    No Git operations, only adds a comment.

    Args:
        issue_data: Plane issue data from webhook

    Returns:
        Workflow result dict
    """
    issue_identifier = extract_issue_identifier(issue_data)
    issue_id = str(issue_data.get("id", ""))

    logger.info(f"[Testing Failed] Processing issue {issue_identifier}")

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    comment_html = f"""<h3 style="color:#ff4d4f;">Testing Failed</h3>
<div style="background:#fff1f0;border:1px solid #ff4d4f;padding:12px;border-radius:4px;">
<p><strong>Time:</strong> {current_time}</p>
<p>Issue has been returned to development. Please fix the issues and re-submit for testing.</p>
</div>"""

    project_id = settings.plane_project_id
    result = await plane_service.add_comment(project_id, issue_id, comment_html)

    if result:
        logger.info(f"[Testing Failed] Notification sent for {issue_identifier}")
    else:
        logger.error(f"[Testing Failed] Failed to send notification for {issue_identifier}")

    return {"status": "completed", "issue_identifier": issue_identifier}
