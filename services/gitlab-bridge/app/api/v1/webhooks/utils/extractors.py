"""
Data extraction utilities for Plane webhooks

Key difference from jira-scripts:
- Feature branches are found via GitLab API search (not from Jira comments)
- Modules are matched by Plane Label names (not Jira Component names)
"""

import logging
from typing import Any, Dict, List

from app.services.gitlab_service import gitlab_service
from app.services.module_config_service import module_config_service
from app.services.plane_service import plane_service


logger = logging.getLogger(__name__)


def extract_labels(issue_data: Dict[str, Any]) -> List[str]:
    """
    Extract label names from Plane issue data

    Args:
        issue_data: Plane issue object from webhook payload

    Returns:
        List of label name strings
    """
    return plane_service.get_labels_from_issue(issue_data)


def match_modules_by_labels(labels: List[str]) -> list:
    """
    Match Plane labels to module configurations

    Args:
        labels: List of label names from the issue

    Returns:
        List of ModuleConfig objects that match
    """
    return module_config_service.get_modules_for_labels(labels)


def extract_issue_identifier(issue_data: Dict[str, Any]) -> str:
    """
    Extract issue identifier (e.g., 'PROJ-123') from Plane issue data

    Args:
        issue_data: Plane issue object

    Returns:
        Issue identifier string
    """
    # Plane issue data contains 'project_detail.identifier' and 'sequence_id'
    project_detail = issue_data.get("project_detail", {})
    project_identifier = project_detail.get("identifier", "")
    sequence_id = issue_data.get("sequence_id", "")

    if project_identifier and sequence_id:
        return f"{project_identifier}-{sequence_id}"

    # Fallback: try to use the identifier field directly if available
    return issue_data.get("identifier", str(issue_data.get("id", "")))


async def find_feature_branches(issue_identifier: str, modules: list) -> Dict[str, str]:
    """
    Find feature branches for an issue across all modules using GitLab API search.

    This replaces jira-scripts' extract_feature_branches() which parsed Jira comments.
    Instead, we directly search GitLab for branches matching the issue identifier.

    Args:
        issue_identifier: Issue identifier (e.g., 'PROJ-123')
        modules: List of ModuleConfig to search

    Returns:
        Dict[module_name, branch_name]
        e.g.: {"repo:admin-web": "feature/PROJ-123_20250101_some-desc"}
    """
    branches = {}

    for module in modules:
        project_id = module.gitlab.project_id
        branch_name = gitlab_service.branches.get_first_story_branch(project_id, issue_identifier)

        if branch_name:
            branches[module.name] = branch_name
            logger.info(f"Found branch for {issue_identifier} in {module.name}: {branch_name}")
        else:
            logger.debug(f"No branch found for {issue_identifier} in {module.name}")

    logger.info(f"Found {len(branches)} branches for issue {issue_identifier}")
    return branches


def extract_repositories_from_issues(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Extract repository info from issue list (via labels → module config)

    Replaces jira-scripts version which used JIRA components.

    Args:
        issues: List of Plane issue objects

    Returns:
        Dict[project_id, issue_count]
    """
    repository_issues = {}

    for issue in issues:
        issue_id = extract_issue_identifier(issue)
        labels = extract_labels(issue)

        if not labels:
            logger.debug(f"Issue {issue_id} has no labels, skipping")
            continue

        modules = match_modules_by_labels(labels)
        for module in modules:
            project_id = module.gitlab.project_id
            if project_id not in repository_issues:
                repository_issues[project_id] = 0
            repository_issues[project_id] += 1

    logger.info(f"Extracted {len(repository_issues)} repositories from {len(issues)} issues")
    return repository_issues
