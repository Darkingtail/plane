"""
Settings Service - Read/write GitLab settings from JSON file
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SETTINGS_FILE = Path(__file__).parent.parent.parent / "config" / "gitlab-settings.json"

DEFAULT_SETTINGS = {
    "gitlab_url": "",
    "token": "",
    "enabled_repos": []
}


class SettingsService:
    """Service to manage GitLab settings stored in a JSON file."""

    def load(self) -> dict:
        """Load settings from JSON file, return defaults if not exists."""
        if not SETTINGS_FILE.exists():
            logger.debug(f"Settings file not found at {SETTINGS_FILE}, returning defaults")
            return dict(DEFAULT_SETTINGS)
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults so any missing keys are filled in
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except Exception as e:
            logger.error(f"Failed to load settings from {SETTINGS_FILE}: {e}")
            return dict(DEFAULT_SETTINGS)

    def save(self, data: dict) -> None:
        """Save settings to JSON file."""
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Settings saved to {SETTINGS_FILE}")
        except Exception as e:
            logger.error(f"Failed to save settings to {SETTINGS_FILE}: {e}")
            raise

    def get_gitlab_url(self) -> str:
        return self.load().get("gitlab_url", "")

    def get_token(self) -> str:
        return self.load().get("token", "")

    def get_enabled_repos(self) -> list[str]:
        return self.load().get("enabled_repos", [])


settings_service = SettingsService()
