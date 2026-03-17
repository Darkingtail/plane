"""
Webhook event validation utilities
"""

import logging
from typing import Any, Dict


logger = logging.getLogger(__name__)


def is_state_change(payload: Dict[str, Any]) -> bool:
    """
    Check if the webhook payload represents an issue state change

    Args:
        payload: Plane webhook payload

    Returns:
        True if this is a state change event
    """
    event = payload.get("event")
    action = payload.get("action")
    activity = payload.get("activity", {})

    if event != "issue" or action not in ("update", "updated"):
        return False

    return activity.get("field") in ("state", "state_id")


def is_label_change(payload: Dict[str, Any]) -> bool:
    """
    Check if the webhook payload represents an issue label change

    Args:
        payload: Plane webhook payload

    Returns:
        True if this is a label change event
    """
    event = payload.get("event")
    action = payload.get("action")
    activity = payload.get("activity", {})

    if event != "issue" or action != "update":
        return False

    return activity.get("field") == "label"


def is_issue_created(payload: Dict[str, Any]) -> bool:
    """
    Check if the webhook payload represents a new issue creation

    Args:
        payload: Plane webhook payload

    Returns:
        True if this is a new issue creation event
    """
    return payload.get("event") == "issue" and payload.get("action") == "create"


def is_release_issue(issue_data: Dict[str, Any]) -> bool:
    """
    Check if an issue is a release/freeze issue (by label)

    Args:
        issue_data: Plane issue data

    Returns:
        True if the issue has a 'type:release' label
    """
    labels = issue_data.get("label_detail", [])
    label_names = [label.get("name", "") for label in labels if label.get("name")]
    return "type:release" in label_names
