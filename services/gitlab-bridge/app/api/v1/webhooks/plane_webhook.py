"""
Plane Webhook Handler

Main entry point for Plane webhook events.
Routes issue state changes to appropriate workflow handlers.

Plane webhook payload format:
{
    "event": "issue",
    "action": "update",
    "webhook_id": "<uuid>",
    "workspace_id": "<uuid>",
    "data": { /* full issue object */ },
    "activity": {
        "field": "state",
        "old_value": "Todo",
        "new_value": "In Progress",
        "old_identifier": "<old-state-uuid>",
        "new_identifier": "<new-state-uuid>"
    }
}
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.models.webhook import PlaneWebhookPayload

from .utils.signature import verify_signature
from .utils.validators import is_release_issue, is_state_change
from app.core.config import settings as app_settings
from app.services.plane_service import plane_service


logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/plane/issue")
async def plane_issue_webhook(request: Request):
    """
    Handle Plane issue webhook events

    Processes issue state changes and routes to appropriate workflows:
    - → Integrating: feature → dev merge
    - → Testing: feature → test merge
    - Testing → In Progress: testing failed notification
    - → To Publish: test passed recording
    - Release issue state changes: freeze/release workflows
    """
    # 1. Read raw body for signature verification
    raw_body = await request.body()

    # 2. Verify signature
    signature = request.headers.get("X-Plane-Signature", "")
    if not verify_signature(raw_body, signature):
        logger.warning("Webhook signature verification failed")
        return JSONResponse(status_code=401, content={"error": "Invalid signature"})

    # 3. Parse payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Failed to parse webhook payload")
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    # 4. Validate and extract event info
    event = payload.get("event", "")
    action = payload.get("action", "")
    activity = payload.get("activity", {})

    logger.info(f"Webhook received: event={event}, action={action}, field={activity.get('field')}")
    logger.debug(f"Activity detail: {activity}")

    # Handle sub-issue "创建分支" completion
    if is_state_change(payload):
        sub_result = await maybe_handle_branch_creation_subtask(payload)
        if sub_result is not None:
            return {"status": "processed", "result": sub_result}

    # Only process issue update events with state changes
    if not is_state_change(payload):
        return {"status": "ignored", "reason": "not a state change"}

    # 5. Extract state change info — values may be UUIDs or names
    old_state_raw = activity.get("old_value", "")
    new_state_raw = activity.get("new_value", "")
    issue_data = payload.get("data", {})

    # Enrich issue_data: webhook payload often has empty label_detail
    # Fetch full issue from Plane API to get label_detail populated
    issue_id = str(issue_data.get("id", ""))
    if issue_id and not issue_data.get("label_detail") and issue_data.get("labels"):
        enriched = await plane_service.get_issue(app_settings.plane_project_id, issue_id)
        if enriched:
            issue_data = enriched

    # Resolve UUIDs to state names if needed
    project_id = app_settings.plane_project_id
    old_state = await _resolve_state_name(old_state_raw, project_id)
    new_state = await _resolve_state_name(new_state_raw, project_id)

    logger.info(f"State change: '{old_state}' → '{new_state}'")

    # 6. Route to appropriate workflow
    try:
        result = await route_state_change(old_state, new_state, issue_data)
        return {"status": "processed", "result": result}
    except Exception as e:
        logger.error(f"Workflow error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Workflow processing failed", "detail": str(e)},
        )


async def route_state_change(
    old_state: str, new_state: str, issue_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Route state change to appropriate workflow handler

    Args:
        old_state: Previous state name
        new_state: New state name
        issue_data: Plane issue data

    Returns:
        Workflow result dict
    """
    # Check if this is a release issue (has 'type:release' label)
    if is_release_issue(issue_data):
        return await route_release_workflow(old_state, new_state, issue_data)

    # Standard issue workflows
    return await route_standard_workflow(old_state, new_state, issue_data)


async def route_standard_workflow(
    old_state: str, new_state: str, issue_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Route standard issue state changes"""

    # → Integrating: feature → dev merge
    if new_state == settings.state_integrating:
        from .workflows.integrating import handle_integrating

        return await handle_integrating(issue_data)

    # → Testing: feature → test merge
    if new_state == settings.state_testing:
        from .workflows.testing import handle_testing

        return await handle_testing(issue_data)

    # Testing → In Progress: testing failed
    if old_state == settings.state_testing and new_state == settings.state_developing:
        from .workflows.testing_failed import handle_testing_failed

        return await handle_testing_failed(issue_data)

    # → To Publish: test passed
    if new_state == settings.state_to_publish:
        from .workflows.to_publish import handle_to_publish

        return await handle_to_publish(issue_data)

    logger.debug(f"No workflow for state change: '{old_state}' → '{new_state}'")
    return {"status": "ignored", "reason": f"no workflow for '{old_state}' → '{new_state}'"}


async def route_release_workflow(
    old_state: str, new_state: str, issue_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Route release issue state changes"""
    from .workflows.release import (
        handle_freeze_complete,
        handle_freeze_execute,
        handle_release_publish,
    )

    # Freeze Execute: e.g., "Freeze Ready" → "Regressing"
    # The exact state names depend on user configuration
    # For now, we use Integrating as trigger for freeze execute
    if new_state == settings.state_integrating:
        return await handle_freeze_execute(issue_data)

    # Freeze Complete: e.g., "Regressing" → "To Publish"
    if new_state == settings.state_to_publish:
        return await handle_freeze_complete(issue_data)

    # Release Publish: e.g., "To Publish" → "Done"
    if new_state == settings.state_done:
        return await handle_release_publish(issue_data)

    logger.debug(f"No release workflow for: '{old_state}' → '{new_state}'")
    return {"status": "ignored", "reason": f"no release workflow for '{old_state}' → '{new_state}'"}


async def _resolve_state_name(value: str, project_id: str) -> str:
    """If value looks like a UUID, resolve it to state name; otherwise return as-is."""
    import re
    if re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", value or ""):
        name = await plane_service.get_state_name(project_id, value)
        return name or value
    return value


async def maybe_handle_branch_creation_subtask(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    If this is a "创建分支" sub-issue being moved to Done,
    fetch the parent issue and trigger branch creation.

    Returns the workflow result if handled, or None to continue normal routing.
    """
    activity = payload.get("activity", {})
    new_state = activity.get("new_value", "")
    issue_data = payload.get("data", {})

    # Only trigger on Done state
    if new_state != settings.state_done:
        return None

    # Check if this issue's name contains the trigger keyword
    issue_name = issue_data.get("name", "") or issue_data.get("title", "")
    if "创建分支" not in issue_name:
        return None

    # It's a "创建分支" sub-issue — find parent issue
    parent_id = issue_data.get("parent")
    if not parent_id:
        logger.info(f"[BranchCreation] '创建分支' issue has no parent, skipping")
        return None

    project_id = app_settings.plane_project_id
    logger.info(f"[BranchCreation] '创建分支' sub-issue done, fetching parent {parent_id}")

    parent_issue = await plane_service.get_issue(project_id, parent_id)
    if not parent_issue:
        logger.error(f"[BranchCreation] Could not fetch parent issue {parent_id}")
        return {"status": "error", "reason": "could not fetch parent issue"}

    from .workflows.branch_creation import handle_branch_creation
    return await handle_branch_creation(parent_issue)
