"""
System endpoints - health check, info, debug tools
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.cache_service import cache_service


router = APIRouter(tags=["system"])


@router.get("/system/health")
async def system_health():
    """Detailed health check"""
    cache_health = await cache_service.health_check()
    return {
        "status": "healthy",
        "service": "plane-gitlab-bridge",
        "cache": cache_health,
    }


class CreateBranchRequest(BaseModel):
    issue_identifier: str  # e.g. "WISFE-8"
    issue_id: str          # Plane issue UUID


@router.post("/debug/create-branch")
async def debug_create_branch(body: CreateBranchRequest):
    """
    Manually trigger branch creation for a Plane issue.
    Fetches the issue from Plane API and runs the branch creation workflow.
    Debug endpoint — useful for testing without triggering a real webhook.
    """
    from app.core.config import settings
    from app.services.plane_service import plane_service
    from app.api.v1.webhooks.workflows.branch_creation import handle_branch_creation

    issue_data = await plane_service.get_issue(settings.plane_project_id, body.issue_id)
    if not issue_data:
        return {"status": "error", "reason": f"Issue {body.issue_id} not found"}

    # GET /issues/<id>/ doesn't return project_detail — inject identifier from request
    if not issue_data.get("project_detail"):
        parts = body.issue_identifier.split("-", 1)
        issue_data["project_detail"] = {"identifier": parts[0]}
        if len(parts) > 1 and not issue_data.get("sequence_id"):
            try:
                issue_data["sequence_id"] = int(parts[1])
            except ValueError:
                pass

    return await handle_branch_creation(issue_data)
