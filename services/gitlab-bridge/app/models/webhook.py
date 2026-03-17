"""
Plane Webhook data models
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class PlaneWebhookActivity(BaseModel):
    """Activity data in Plane webhook payload"""

    field: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    old_identifier: Optional[str] = None
    new_identifier: Optional[str] = None

    class Config:
        extra = "allow"


class PlaneWebhookPayload(BaseModel):
    """
    Plane Webhook payload structure

    Example:
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

    event: str = Field(..., description="Event type: 'issue', 'project', etc.")
    action: str = Field(..., description="Action: 'create', 'update', 'delete'")
    webhook_id: Optional[str] = None
    workspace_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict, description="Full issue/entity object")
    activity: Optional[PlaneWebhookActivity] = None

    class Config:
        extra = "allow"


class WebhookResponse(BaseModel):
    """Response for webhook processing"""

    success: bool
    message: str
    event_type: str
    issue_identifier: Optional[str] = None
    processed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    details: Optional[Dict[str, Any]] = None
