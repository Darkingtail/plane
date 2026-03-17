"""
GitLab Settings API endpoints

Provides CRUD operations for GitLab connection settings, connection testing,
and repository listing. Settings are persisted to config/gitlab-settings.json.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.settings_service import settings_service


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class GitLabSettingsResponse(BaseModel):
    gitlab_url: str
    token_set: bool
    token_preview: str
    enabled_repos: List[str]


class GitLabSettingsUpdate(BaseModel):
    gitlab_url: str
    token: Optional[str] = None
    enabled_repos: List[str] = []


class GitLabTestRequest(BaseModel):
    gitlab_url: str
    token: str


class GitLabTestResponse(BaseModel):
    success: bool
    username: Optional[str] = None
    name: Optional[str] = None
    api_version: Optional[str] = None
    error: Optional[str] = None


class RepoInfo(BaseModel):
    id: int
    name: str
    path: str
    ssh_url: str
    http_url: str
    enabled: bool


class ReposResponse(BaseModel):
    api_version: str
    namespaces: Dict[str, List[RepoInfo]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mask_token(token: str) -> str:
    """Return first 3 chars + *** + last 3 chars, or empty string."""
    if not token:
        return ""
    if len(token) <= 6:
        return "***"
    return f"{token[:3]}***{token[-3:]}"


def _build_settings_response() -> GitLabSettingsResponse:
    token = settings_service.get_token()
    return GitLabSettingsResponse(
        gitlab_url=settings_service.get_gitlab_url(),
        token_set=bool(token),
        token_preview=_mask_token(token),
        enabled_repos=settings_service.get_enabled_repos(),
    )


async def _detect_api_version(client: httpx.AsyncClient, gitlab_url: str, token: str) -> str:
    """Try v4 first, fall back to v3. Returns 'v4' or 'v3'."""
    headers = {"PRIVATE-TOKEN": token}
    try:
        resp = await client.get(f"{gitlab_url}/api/v4/user", headers=headers)
        if resp.status_code == 200:
            return "v4"
        if resp.status_code == 404:
            resp2 = await client.get(f"{gitlab_url}/api/v3/user", headers=headers)
            if resp2.status_code == 200:
                return "v3"
    except Exception:
        pass
    return "v4"  # default attempt


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/gitlab", response_model=GitLabSettingsResponse)
async def get_gitlab_settings():
    """Return current GitLab settings. Token is masked in the response."""
    return _build_settings_response()


@router.put("/gitlab", response_model=GitLabSettingsResponse)
async def update_gitlab_settings(body: GitLabSettingsUpdate):
    """
    Save GitLab settings.

    If `token` is an empty string or omitted, the existing token is preserved.
    """
    current = settings_service.load()

    new_data = {
        "gitlab_url": body.gitlab_url.rstrip("/") if body.gitlab_url else "",
        "token": body.token if body.token else current.get("token", ""),
        "enabled_repos": body.enabled_repos,
    }
    settings_service.save(new_data)
    return _build_settings_response()


@router.post("/gitlab/test", response_model=GitLabTestResponse)
async def test_gitlab_connection(body: GitLabTestRequest):
    """
    Test GitLab connection with the provided URL and token.

    Tries v4 /user endpoint first, falls back to v3.
    """
    gitlab_url = body.gitlab_url.rstrip("/")
    token = body.token
    headers = {"PRIVATE-TOKEN": token}

    async with httpx.AsyncClient(timeout=15) as client:
        # Try v4
        try:
            resp = await client.get(f"{gitlab_url}/api/v4/user", headers=headers)
            if resp.status_code == 200:
                user = resp.json()
                return GitLabTestResponse(
                    success=True,
                    username=user.get("username"),
                    name=user.get("name"),
                    api_version="v4",
                )
            if resp.status_code != 404:
                return GitLabTestResponse(
                    success=False,
                    error=f"GitLab API v4 returned HTTP {resp.status_code}",
                )
        except httpx.RequestError as e:
            return GitLabTestResponse(success=False, error=f"Connection error: {e}")

        # Fall back to v3
        try:
            resp = await client.get(f"{gitlab_url}/api/v3/user", headers=headers)
            if resp.status_code == 200:
                user = resp.json()
                return GitLabTestResponse(
                    success=True,
                    username=user.get("username"),
                    name=user.get("name"),
                    api_version="v3",
                )
            return GitLabTestResponse(
                success=False,
                error=f"GitLab API v3 returned HTTP {resp.status_code}",
            )
        except httpx.RequestError as e:
            return GitLabTestResponse(success=False, error=f"Connection error (v3): {e}")


@router.get("/gitlab/repos", response_model=ReposResponse)
async def list_gitlab_repos():
    """
    List all accessible GitLab repositories using the stored token.

    Tries v4 API first, falls back to v3. Results are grouped by namespace.
    """
    gitlab_url = settings_service.get_gitlab_url()
    token = settings_service.get_token()

    if not gitlab_url:
        raise HTTPException(status_code=400, detail="GitLab URL is not configured")
    if not token:
        raise HTTPException(status_code=400, detail="GitLab token is not configured")

    gitlab_url = gitlab_url.rstrip("/")
    headers = {"PRIVATE-TOKEN": token}
    enabled_repos = set(settings_service.get_enabled_repos())

    async with httpx.AsyncClient(timeout=30) as client:
        projects: List[dict] = []
        api_version = "v4"

        # Try v4
        try:
            resp = await client.get(
                f"{gitlab_url}/api/v4/projects",
                headers=headers,
                params={"membership": "true", "per_page": 100},
            )
            if resp.status_code == 200:
                projects = resp.json()
                api_version = "v4"
            elif resp.status_code == 404:
                # Fall back to v3
                resp3 = await client.get(
                    f"{gitlab_url}/api/v3/projects",
                    headers=headers,
                    params={"per_page": 100},
                )
                if resp3.status_code == 200:
                    projects = resp3.json()
                    api_version = "v3"
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=f"GitLab API v3 returned HTTP {resp3.status_code}",
                    )
            else:
                raise HTTPException(
                    status_code=502,
                    detail=f"GitLab API v4 returned HTTP {resp.status_code}",
                )
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Connection error: {e}")

        # Group by namespace
        namespaces: Dict[str, List[RepoInfo]] = {}
        for proj in projects:
            path_with_ns = proj.get("path_with_namespace", "")
            parts = path_with_ns.split("/", 1)
            namespace = parts[0] if len(parts) >= 1 else "unknown"

            repo_info = RepoInfo(
                id=proj.get("id", 0),
                name=proj.get("name", ""),
                path=path_with_ns,
                ssh_url=proj.get("ssh_url_to_repo", ""),
                http_url=proj.get("http_url_to_repo", ""),
                enabled=path_with_ns in enabled_repos,
            )

            if namespace not in namespaces:
                namespaces[namespace] = []
            namespaces[namespace].append(repo_info)

        return ReposResponse(api_version=api_version, namespaces=namespaces)
