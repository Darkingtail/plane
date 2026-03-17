"""
Plane Service - API client for Plane project management

Replaces jira_service from the original jira-scripts project.
Uses Plane's REST API with X-Api-Key authentication.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.cache_service import cache_service


logger = logging.getLogger(__name__)


class PlaneService:
    """Plane API client"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._state_cache: Dict[str, str] = {}  # state_name -> state_id
        self._project_identifier: Optional[str] = None  # cached project identifier

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.plane_base_url.rstrip("/"),
                headers={
                    "X-Api-Key": settings.plane_api_key,
                    "Content-Type": "application/json",
                },
                timeout=settings.api_timeout,
            )
        return self._client

    def _api_path(self, path: str) -> str:
        """Build API path with workspace slug"""
        slug = settings.plane_workspace_slug
        return f"/api/v1/workspaces/{slug}/{path.lstrip('/')}"

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ========================================================================
    # Issues
    # ========================================================================

    async def get_project_identifier(self, project_id: str) -> Optional[str]:
        """Get project identifier (e.g. 'WISFE') by project UUID, cached."""
        if self._project_identifier:
            return self._project_identifier
        try:
            resp = await self.client.get(self._api_path(f"projects/{project_id}/"))
            resp.raise_for_status()
            data = resp.json()
            self._project_identifier = data.get("identifier")
            return self._project_identifier
        except Exception as e:
            logger.error(f"Failed to get project identifier: {e}")
            return None

    async def get_issue(self, project_id: str, issue_id: str) -> Optional[Dict[str, Any]]:
        """Get issue details with label_detail and project_detail populated"""
        try:
            resp = await self.client.get(self._api_path(f"projects/{project_id}/issues/{issue_id}/"))
            resp.raise_for_status()
            issue = resp.json()

            # Inject label_detail if missing
            label_ids = issue.get("labels", [])
            if label_ids and not issue.get("label_detail"):
                labels = await self.list_labels(project_id)
                label_map = {l["id"]: l for l in labels}
                issue["label_detail"] = [label_map[lid] for lid in label_ids if lid in label_map]

            # Inject project_detail if missing (needed for extract_issue_identifier)
            if not issue.get("project_detail"):
                identifier = await self.get_project_identifier(project_id)
                if identifier:
                    issue["project_detail"] = {"identifier": identifier}

            return issue
        except Exception as e:
            logger.error(f"Failed to get issue {issue_id}: {e}")
            return None

    async def update_issue_state(self, project_id: str, issue_id: str, state_id: str) -> bool:
        """Update issue state"""
        try:
            resp = await self.client.patch(
                self._api_path(f"projects/{project_id}/issues/{issue_id}/"),
                json={"state_id": state_id},
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to update issue {issue_id} state: {e}")
            return False

    async def list_issues(
        self, project_id: str, state_id: Optional[str] = None, label_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """List issues with optional filters"""
        try:
            params = {}
            if state_id:
                params["state"] = state_id
            resp = await self.client.get(
                self._api_path(f"projects/{project_id}/issues/"),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Failed to list issues: {e}")
            return []

    # ========================================================================
    # Comments
    # ========================================================================

    async def add_comment(self, project_id: str, issue_id: str, comment_html: str) -> Optional[Dict[str, Any]]:
        """Add comment to an issue (HTML format)"""
        try:
            resp = await self.client.post(
                self._api_path(f"projects/{project_id}/issues/{issue_id}/comments/"),
                json={"comment_html": comment_html},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to add comment to issue {issue_id}: {e}")
            return None

    # ========================================================================
    # States
    # ========================================================================

    async def list_states(self, project_id: str) -> List[Dict[str, Any]]:
        """List all states for a project"""
        try:
            resp = await self.client.get(self._api_path(f"projects/{project_id}/states/"))
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Failed to list states: {e}")
            return []

    async def get_state_id(self, project_id: str, state_name: str) -> Optional[str]:
        """Get state UUID by name (cached)"""
        cache_key = f"plane:state:{project_id}:{state_name}"

        # Check in-memory cache
        if state_name in self._state_cache:
            return self._state_cache[state_name]

        # Check Redis cache
        cached = await cache_service.get(cache_key)
        if cached:
            self._state_cache[state_name] = cached
            return cached

        # Fetch from API and populate both name→id and id→name caches
        states = await self.list_states(project_id)
        result = None
        for state in states:
            sid = state["id"]
            sname = state.get("name", "")
            self._state_cache[sname] = sid
            self._state_cache[sid] = sname  # reverse mapping
        if state_name in self._state_cache:
            result = self._state_cache[state_name]
            await cache_service.set(cache_key, result, ttl=settings.cache_ttl_states)
            return result

        logger.warning(f"State '{state_name}' not found in project {project_id}")
        return None

    async def get_state_name(self, project_id: str, state_id: str) -> Optional[str]:
        """Get state name by UUID (reverse lookup, cached)"""
        if state_id in self._state_cache:
            return self._state_cache[state_id]
        # Populate cache by listing states
        states = await self.list_states(project_id)
        for state in states:
            sid = state["id"]
            sname = state.get("name", "")
            self._state_cache[sid] = sname
            self._state_cache[sname] = sid
        return self._state_cache.get(state_id)

    # ========================================================================
    # Labels
    # ========================================================================

    async def list_labels(self, project_id: str) -> List[Dict[str, Any]]:
        """List all labels for a project"""
        try:
            resp = await self.client.get(self._api_path(f"projects/{project_id}/labels/"))
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Failed to list labels: {e}")
            return []

    @staticmethod
    def get_labels_from_issue(issue_data: Dict[str, Any]) -> List[str]:
        """Extract label names from issue data"""
        labels = issue_data.get("label_detail", [])
        return [label.get("name", "") for label in labels if label.get("name")]


plane_service = PlaneService()
