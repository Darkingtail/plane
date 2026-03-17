"""
GitLab Service 基础类

提供会话管理、API 版本检测、URL/Headers 构建等基础功能
"""

import logging
from typing import Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.services.module_config_service import module_config_service


logger = logging.getLogger(__name__)


class GitLabServiceBase:
    """GitLab Service 基础类"""

    def __init__(self):
        self._api_version: Optional[str] = None
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            config = module_config_service.config
            retry_strategy = Retry(
                total=config.gitlab.max_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    @property
    def api_version(self) -> str:
        if self._api_version is None:
            config = module_config_service.config
            token = module_config_service.get_gitlab_token()
            if not token:
                raise ValueError("GitLab token not configured")
            headers = {"PRIVATE-TOKEN": token}
            gitlab_url = module_config_service.get_gitlab_url()
            try:
                response = self.session.get(f"{gitlab_url}/api/v4/user", headers=headers, timeout=config.gitlab.timeout)
                if response.status_code == 200:
                    self._api_version = "v4"
                    logger.info("Detected GitLab API v4")
                elif response.status_code == 404:
                    response = self.session.get(
                        f"{gitlab_url}/api/v3/user", headers=headers, timeout=config.gitlab.timeout
                    )
                    if response.status_code == 200:
                        self._api_version = "v3"
                        logger.info("Detected GitLab API v3 (older version)")
                    else:
                        raise Exception(f"Cannot detect GitLab API version: {response.status_code}")
                else:
                    raise Exception(f"GitLab API error: {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to detect GitLab API version: {e}")
                raise
        return self._api_version

    def _get_api_url(self, path: str) -> str:
        gitlab_url = module_config_service.get_gitlab_url()
        path = path.lstrip("/")
        return f"{gitlab_url}/api/{self.api_version}/{path}"

    def _get_headers(self) -> Dict[str, str]:
        token = module_config_service.get_gitlab_token()
        if not token:
            raise ValueError("GitLab token not configured")
        return {"PRIVATE-TOKEN": token}

    def _get_timeout(self) -> int:
        return module_config_service.config.gitlab.timeout
