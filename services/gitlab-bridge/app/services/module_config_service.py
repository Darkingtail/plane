"""
Module Configuration Service - Load and manage module-to-GitLab mapping

Plane version: uses Label names instead of JIRA Component names for module matching.
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from app.core.constants import BASE_DIR


logger = logging.getLogger(__name__)


class BranchModel(BaseModel):
    """Branch naming model for workflow branches"""
    main: Optional[str] = Field(None, description="Production branch name")
    release: Optional[str] = Field(None, description="Release branch name")
    test: Optional[str] = Field(None, description="Test environment branch name")
    dev: Optional[str] = Field(None, description="Development/integration branch name")


class GitLabConfig(BaseModel):
    """GitLab repository configuration"""
    project_id: str = Field(..., description="GitLab project ID or group/project path")
    repository_url: Optional[str] = Field(None, description="Repository URL for documentation")
    branches: Optional[BranchModel] = Field(None, description="Custom branch names (overrides workflow.branches)")


class ModuleConfig(BaseModel):
    """Module configuration - matched by Plane Label name"""
    name: str = Field(..., description="Module name (must match a Plane Label name)")
    display_name: str = Field(..., description="Display name")
    gitlab: GitLabConfig
    enabled: bool = Field(default=True, description="Whether this module is enabled")


class GitLabGlobalConfig(BaseModel):
    """Global GitLab settings"""
    url: Optional[str] = Field(None, description="GitLab server URL")
    url_env: Optional[str] = Field(None, description="Environment variable for GitLab URL")
    token_env: str = Field(default="GITLAB_TOKEN", description="Environment variable for token")
    branch_name_template: str = Field(default="feature/{issue_identifier}", description="Branch name template")
    timeout: int = Field(default=30, description="API timeout in seconds")
    max_retries: int = Field(default=3, description="Max retry attempts")


class BranchCreationConfig(BaseModel):
    """Branch creation rules"""
    check_existence: bool = Field(default=True)
    if_exists: str = Field(default="skip", description="Action if branch exists: skip/overwrite/error")
    add_plane_comment: bool = Field(default=True, description="Add comment to Plane after creation")
    comment_template: str = Field(default="", description="Plane comment template (HTML)")


class WorkflowConfig(BaseModel):
    """Workflow configuration with default branch naming"""
    branches: BranchModel = Field(
        default_factory=lambda: BranchModel(main="main", release="release", test="test", dev="dev"),
    )


class ModulesConfiguration(BaseModel):
    """Complete modules configuration"""
    modules: List[ModuleConfig]
    gitlab: GitLabGlobalConfig
    branch_creation: BranchCreationConfig
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)


class ModuleConfigService:
    """Service to manage module configuration"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = BASE_DIR / "config" / "modules.yml"
        self.config_path = Path(config_path)
        self._config: Optional[ModulesConfiguration] = None
        self._module_map: Dict[str, ModuleConfig] = {}
        self._config_mtime: float = 0.0

    def load_config(self) -> ModulesConfiguration:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        logger.info(f"Loading module configuration from {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        self._config = ModulesConfiguration(**yaml_data)
        self._module_map = {module.name: module for module in self._config.modules if module.enabled}
        self._config_mtime = self.config_path.stat().st_mtime
        logger.info(f"Loaded {len(self._module_map)} enabled modules")
        return self._config

    def reload_config(self) -> ModulesConfiguration:
        logger.info("Reloading module configuration from file...")
        self._config = None
        self._module_map = {}
        loaded_config = self.load_config()
        logger.info(f"Successfully reloaded {len(self._module_map)} enabled modules")
        return loaded_config

    @property
    def config(self) -> ModulesConfiguration:
        if self._config is not None and self.config_path.exists():
            current_mtime = self.config_path.stat().st_mtime
            if current_mtime > self._config_mtime:
                logger.info("Config file changed, auto-reloading...")
                self.reload_config()
        if self._config is None:
            self.load_config()
        return self._config

    def get_module(self, module_name: str) -> Optional[ModuleConfig]:
        if not self._module_map:
            self.load_config()
        return self._module_map.get(module_name)

    def get_enabled_modules(self) -> List[ModuleConfig]:
        if not self._module_map:
            self.load_config()
        return list(self._module_map.values())

    def get_gitlab_url(self) -> str:
        if self.config.gitlab.url_env:
            url = os.getenv(self.config.gitlab.url_env)
            if not url:
                try:
                    from dotenv import load_dotenv
                    env_path = BASE_DIR / ".env"
                    if env_path.exists():
                        load_dotenv(env_path)
                        url = os.getenv(self.config.gitlab.url_env)
                except ImportError:
                    pass
            if url:
                return url.rstrip("/")
        if self.config.gitlab.url:
            return self.config.gitlab.url.rstrip("/")
        raise ValueError("GitLab URL not configured")

    def get_gitlab_token(self) -> Optional[str]:
        token_env = self.config.gitlab.token_env
        token = os.getenv(token_env)
        if not token:
            try:
                from dotenv import load_dotenv
                env_path = BASE_DIR / ".env"
                if env_path.exists():
                    load_dotenv(env_path)
                    token = os.getenv(token_env)
            except ImportError:
                pass
        if not token:
            logger.warning(f"GitLab token not found in environment variable: {token_env}")
        return token

    def format_branch_name(
        self,
        issue_identifier: str,
        issue_name: str = "",
    ) -> str:
        """Format branch name using template"""
        import re
        from datetime import datetime

        date_str = datetime.now().strftime("%Y%m%d")
        source_text = issue_name.strip() if issue_name else ""
        source_text = re.sub(r"^\s*[\[【][^\]】]+[\]】]\s*", "", source_text)
        desc = re.sub(r"[^\w\u4e00-\u9fff\-]", "", source_text)
        desc = desc[:36] if desc else ""

        template = self.config.gitlab.branch_name_template
        return template.format(issue_identifier=issue_identifier, date=date_str, desc=desc)

    def get_modules_for_labels(self, label_names: List[str]) -> List[ModuleConfig]:
        """
        Get module configurations matching the given Plane Label names.

        In Plane, labels replace JIRA components for module matching.
        Label names must exactly match module names in modules.yml.
        """
        valid_modules = []
        for name in label_names:
            module = self.get_module(name)
            if module and module.enabled and module.gitlab.project_id:
                valid_modules.append(module)
            else:
                logger.debug(f"Label '{name}' does not match any enabled module")
        return valid_modules

    def get_branch_name(self, module: ModuleConfig, role: str) -> str:
        DEFAULTS = {"main": "main", "release": "release", "test": "test", "dev": "dev"}
        if module.gitlab.branches:
            branch_value = getattr(module.gitlab.branches, role, None)
            if branch_value:
                return branch_value
        workflow_branches = self.config.workflow.branches
        branch_value = getattr(workflow_branches, role, None)
        if branch_value:
            return branch_value
        return DEFAULTS.get(role, role)

    def get_release_branch(self, module: ModuleConfig) -> str:
        return self.get_branch_name(module, "release")

    def get_dev_branch(self, module: ModuleConfig) -> str:
        return self.get_branch_name(module, "dev")

    def get_test_branch(self, module: ModuleConfig) -> str:
        return self.get_branch_name(module, "test")

    def get_main_branch(self, module: ModuleConfig) -> str:
        return self.get_branch_name(module, "main")

    def get_module_by_project_id(self, project_id: str) -> Optional[ModuleConfig]:
        if not self._module_map:
            self.load_config()
        for module in self._module_map.values():
            if module.gitlab.project_id == project_id:
                return module
        return None

    def should_add_plane_comment(self) -> bool:
        return self.config.branch_creation.add_plane_comment

    def format_comment(self, module: ModuleConfig, branch_name: str, branch_url: str, base_branch: str) -> str:
        template = self.config.branch_creation.comment_template
        return template.format(
            module_name=module.name,
            module_display_name=module.display_name,
            repository_url=module.gitlab.repository_url or module.gitlab.project_id,
            branch_name=branch_name,
            base_branch=base_branch,
            branch_url=branch_url,
        )


module_config_service = ModuleConfigService()
