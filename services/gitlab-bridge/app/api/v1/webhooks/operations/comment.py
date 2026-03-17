"""
Plane comment operations module

Provides comment generation and posting for all workflow phases.
All comments use HTML format (Plane's comment_html field).

Key difference from jira-scripts:
- HTML format instead of Jira/Confluence wiki markup
- Uses plane_service.add_comment() instead of jira_service.add_comment()
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.plane_service import plane_service
from app.services.module_config_service import module_config_service

from .types import MergeResultList


logger = logging.getLogger(__name__)


# ============================================================================
# Story workflow comment functions
# ============================================================================


async def add_merge_comment(
    issue_id: str, target_branch: str, results: MergeResultList
) -> None:
    """
    Record merge results to issue (integration/testing workflow)

    Args:
        issue_id: Plane issue UUID
        target_branch: Target branch name (dev/test)
        results: Merge result list
    """
    success_count = sum(1 for r in results if r.get("success"))
    total = len(results)

    lines = [
        f"<h3>Merged to <code>{target_branch}</code></h3>",
        f"<p>Result: {success_count}/{total} succeeded</p>",
    ]

    # Successful modules
    success_modules = [r for r in results if r.get("success")]
    if success_modules:
        lines.append("<h4>Merged successfully</h4><ul>")
        for r in success_modules:
            commit_sha_short = r.get("commit_sha", "")[:8] if r.get("commit_sha") else "N/A"
            mr_url = r.get("mr_url", "")
            if mr_url:
                lines.append(f'<li>{r["module"]}: <a href="{mr_url}">{commit_sha_short}</a></li>')
            else:
                lines.append(f'<li>{r["module"]}: {commit_sha_short}</li>')
        lines.append("</ul>")

    # Skipped modules (same content)
    skip_modules = [r for r in results if not r.get("success") and r.get("skip_reason") == "same_content"]
    if skip_modules:
        lines.append("<h4>No merge needed</h4><ul>")
        for r in skip_modules:
            mr_url = r.get("mr_url", "")
            mr_closed = r.get("mr_closed", False)
            if mr_closed and mr_url:
                lines.append(f'<li>{r["module"]}: same content, MR auto-closed (<a href="{mr_url}">view MR</a>)</li>')
            elif mr_url:
                lines.append(f'<li>{r["module"]}: same content (<a href="{mr_url}">view MR</a>)</li>')
            else:
                lines.append(f'<li>{r["module"]}: same content</li>')
        lines.append("</ul>")

    # Failed modules
    failed_modules = [r for r in results if not r.get("success") and r.get("skip_reason") != "same_content"]
    if failed_modules:
        lines.append("<h4>Needs attention</h4><ul>")
        for r in failed_modules:
            error = r.get("error", "Unknown error")
            mr_url = r.get("mr_url", "")
            if mr_url:
                lines.append(f'<li>{r["module"]}: {error} (<a href="{mr_url}">view MR</a>)</li>')
            else:
                lines.append(f'<li>{r["module"]}: {error}</li>')
        lines.append("</ul>")

    comment_html = "\n".join(lines)
    project_id = settings.plane_project_id
    await plane_service.add_comment(project_id, issue_id, comment_html)

    logger.info(f"Recorded merge results for issue {issue_id}")


async def notify_conflict(
    issue_id: str,
    module_name: str,
    branch_name: str,
    target_branch: str,
    mr_url: str,
    reason: str,
) -> None:
    """
    Send merge conflict notification as Plane comment

    Args:
        issue_id: Plane issue UUID
        module_name: Module name
        branch_name: Source branch name
        target_branch: Target branch name
        mr_url: MR URL
        reason: Conflict reason
    """
    reason_map = {
        "has_conflicts": "Code conflicts detected",
        "work_in_progress": "MR marked as WIP",
        "not_open": "MR not in open state",
        "cannot_be_merged": "Cannot merge automatically",
        "mr_not_found": "MR not found",
        "merge_status_unchecked": "Merge status unchecked",
    }

    reason_text = reason_map.get(reason, reason)

    comment_html = f"""<h3>Merge Conflict Alert</h3>
<div style="background:#fff1f0;border:1px solid #ff4d4f;padding:12px;border-radius:4px;">
<p><strong>Module:</strong> {module_name}</p>
<p><strong>Branch:</strong> <code>{branch_name}</code> → <code>{target_branch}</code></p>
<p><strong>Reason:</strong> <span style="color:#ff4d4f;">{reason_text}</span></p>
<p><strong>Merge Request:</strong> <a href="{mr_url}">View MR</a></p>
<p style="color:#ff4d4f;">Please resolve the conflict manually and complete the merge in GitLab.</p>
</div>"""

    project_id = settings.plane_project_id
    await plane_service.add_comment(project_id, issue_id, comment_html)
    logger.info(f"Sent conflict notification: {issue_id} - {module_name}")


def format_branch_creation_comment(
    module, branch_name: str, branch_url: str, base_branch: str
) -> str:
    """
    Format branch creation success comment (HTML format)

    Returns:
        HTML comment string
    """
    return module_config_service.format_comment(
        module=module, branch_name=branch_name, branch_url=branch_url, base_branch=base_branch
    )


def format_branch_creation_failure_comment(
    module_name: str, branch_name: str, project_id: Optional[str], error: str
) -> str:
    """
    Format branch creation failure comment (HTML format)

    Returns:
        HTML comment string
    """
    project_line = f"<p><strong>Project:</strong> <code>{project_id}</code></p>" if project_id else ""

    return f"""<h3 style="color:#ff4d4f;">Branch Creation Failed</h3>
<div style="background:#fff1f0;border:1px solid #ff4d4f;padding:12px;border-radius:4px;">
<p><strong>Module:</strong> {module_name}</p>
<p><strong>Branch:</strong> <code>{branch_name}</code></p>
{project_line}
<p><strong>Error:</strong> <span style="color:#ff4d4f;">{error}</span></p>
</div>
<p>Please check GitLab permissions and project configuration, or create the branch manually.</p>"""


# ============================================================================
# Release workflow comment functions
# ============================================================================


async def add_freeze_execute_comment(
    issue_id: str,
    version: str,
    processed_issues: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    repositories: Dict[str, int],
) -> None:
    """
    Add freeze execution result comment to release issue
    """
    total_issues = len(processed_issues)
    total_repos = len(results)
    success_count = sum(1 for r in results if r["success"])
    repo_count = len(repositories)

    lines = [
        "<h3>Freeze Execution Complete</h3>",
        '<div style="background:#e6f7ff;border:1px solid #1890ff;padding:12px;border-radius:4px;">',
        f"<p><strong>Version:</strong> {version}</p>",
        f"<p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        f"<p><strong>Issues processed:</strong> {total_issues}</p>",
        f"<p><strong>Repositories:</strong> {repo_count}</p>",
        f"<p><strong>Merge success:</strong> {success_count}/{total_repos}</p>",
        "</div>",
    ]

    # Issue list
    if processed_issues:
        lines.append("<h4>Issues included</h4><ul>")
        for issue in processed_issues:
            issue_id_str = issue.get("identifier", issue.get("id", ""))
            summary = issue.get("name", "")
            lines.append(f"<li>{issue_id_str}: {summary}</li>")
        lines.append("</ul>")

    # Successful repos
    successful = [r for r in results if r["success"]]
    if successful:
        lines.append("<h4>Merged successfully</h4><ul>")
        for r in successful:
            mr_url = r.get("mr_url", "")
            if mr_url:
                lines.append(f'<li>{r["repository"]}: <a href="{mr_url}">view MR</a></li>')
            else:
                lines.append(f'<li>{r["repository"]}: success</li>')
        lines.append("</ul>")

    # Failed repos
    failed = [r for r in results if not r["success"] and r.get("skip_reason") != "same_content"]
    if failed:
        lines.append("<h4>Merge failed (needs manual handling)</h4><ul>")
        for r in failed:
            error = r.get("error", "Unknown error")
            mr_url = r.get("mr_url", "")
            if mr_url:
                lines.append(f'<li>{r["repository"]}: {error} (<a href="{mr_url}">view MR</a>)</li>')
            else:
                lines.append(f'<li>{r["repository"]}: {error}</li>')
        lines.append("</ul>")

    comment_html = "\n".join(lines)
    project_id = settings.plane_project_id
    await plane_service.add_comment(project_id, issue_id, comment_html)

    logger.info(f"Recorded freeze execution result to {issue_id}")


async def add_freeze_complete_comment(
    issue_id: str, version: str, issue_results: List[Dict[str, Any]]
) -> None:
    """
    Add freeze complete statistics comment to release issue
    """
    total = len(issue_results)
    success_results = [r for r in issue_results if r["success"]]
    failed_results = [r for r in issue_results if not r["success"]]
    with_branches = [r for r in success_results if r.get("branches_total", 0) > 0]
    without_branches = [r for r in success_results if r.get("branches_total", 0) == 0]
    fully_success = [r for r in with_branches if r.get("branches_failed", 0) == 0]

    total_branches = sum(r.get("branches_total", 0) for r in issue_results)
    deleted_branches = sum(r.get("branches_deleted", 0) for r in issue_results)

    lines = [
        "<h3>Freeze Complete</h3>",
        '<div style="background:#f0fff4;border:1px solid #10b981;padding:12px;border-radius:4px;">',
        f"<p><strong>Version:</strong> {version}</p>",
        f"<p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        f"<p><strong>Issues:</strong> {total} total, {len(fully_success)} with branches, {len(without_branches)} without</p>",
        f"<p><strong>Branches:</strong> {total_branches} total, {deleted_branches} deleted</p>",
        "</div>",
    ]

    if failed_results:
        lines.append("<h4>Needs manual handling</h4><ul>")
        for r in failed_results:
            error = r.get("error", "Unknown error")
            lines.append(f'<li>{r["issue_identifier"]}: {r.get("summary", "")} - {error}</li>')
        lines.append("</ul>")

    comment_html = "\n".join(lines)
    project_id = settings.plane_project_id
    await plane_service.add_comment(project_id, issue_id, comment_html)

    logger.info(f"Recorded freeze complete to {issue_id}")


async def add_release_complete_comment(
    issue_id: str, version: str, results: List[Dict[str, Any]]
) -> None:
    """
    Add release complete comment to release issue
    """
    total = len(results)
    success_count = sum(1 for r in results if r.get("success"))

    success_repos = [r for r in results if r.get("success")]
    failed_repos = [r for r in results if not r.get("success")]

    lines = [
        "<h3>Release Published</h3>",
        '<div style="background:#f0fdf4;border:1px solid #22c55e;padding:12px;border-radius:4px;">',
        f"<p><strong>Version:</strong> v{version}</p>",
        f"<p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        f"<p><strong>Repos:</strong> {total} total, {success_count} success, {total - success_count} failed</p>",
        "</div>",
    ]

    if success_repos:
        lines.append("<h4>Released successfully</h4><ul>")
        for r in success_repos:
            repo_id = r["repo_id"]
            tag_info = r.get("tag", {})
            tag_url = tag_info.get("tag_url", "")
            mr_url = r.get("mr_url", "")
            parts = [f"<li>{repo_id}"]
            if mr_url:
                parts.append(f' | <a href="{mr_url}">MR</a>')
            if tag_url:
                parts.append(f' | <a href="{tag_url}">Tag</a>')
            parts.append("</li>")
            lines.append("".join(parts))
        lines.append("</ul>")

    if failed_repos:
        lines.append("<h4>Release failed (needs manual handling)</h4><ul>")
        for r in failed_repos:
            error = r.get("error", "Unknown error")
            lines.append(f'<li>{r["repo_id"]}: {error}</li>')
        lines.append("</ul>")

    comment_html = "\n".join(lines)
    project_id = settings.plane_project_id
    await plane_service.add_comment(project_id, issue_id, comment_html)

    logger.info(f"Recorded release result to {issue_id}")
