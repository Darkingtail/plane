"""
GitLab Service Merge Request 操作模块

提供 MR 的创建、查询、合并、状态检查等功能
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

import requests


if TYPE_CHECKING:
    from .base import GitLabServiceBase

from app.services.module_config_service import module_config_service

from .models import MergeResult


logger = logging.getLogger(__name__)


class MergeRequestOperations:
    """GitLab Merge Request 操作"""

    def __init__(self, base: "GitLabServiceBase"):
        """
        初始化 MR 操作模块

        Args:
            base: GitLabServiceBase 实例
        """
        self.base = base

    def create_merge_request(
        self,
        project_id: str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: Optional[str] = None,
        remove_source_branch: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a Merge Request

        Args:
            project_id: Project ID or namespace/project path
            source_branch: Source branch name
            target_branch: Target branch name
            title: MR title
            description: MR description (optional)
            remove_source_branch: Remove source branch after merge (default: False)

        Returns:
            Dict[str, Any]: Created MR data with fields:
            - v3: id (global ID), iid (project-scoped ID), state, merge_status
            - v4: id, iid, state, has_conflicts

        Example:
            mr = gitlab_service.create_merge_request(
                project_id="wisedu-tech/api-designer",
                source_branch="feature/JSZTF-23_xxx",
                target_branch="dev",
                title="Merge JSZTF-23 to dev"
            )
        """
        try:
            project_id_encoded = project_id.replace("/", "%2F")

            data = {
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "remove_source_branch": remove_source_branch,
            }

            if description:
                data["description"] = description

            response = self.base.session.post(
                self.base._get_api_url(f"projects/{project_id_encoded}/merge_requests"),
                headers=self.base._get_headers(),
                json=data,
                timeout=self.base._get_timeout(),
            )
            response.raise_for_status()

            mr_data = response.json()
            logger.info(f"Created MR #{mr_data.get('iid')} in {project_id}: {title}")
            return mr_data

        except Exception as e:
            logger.error(f"Failed to create MR in {project_id}: {e}")
            return None

    def get_merge_request(self, project_id: str, mr_identifier: int, use_iid: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get Merge Request details

        Args:
            project_id: Project ID or namespace/project path
            mr_identifier: MR identifier
                - v3: use_iid=True for iid, use_iid=False for global id
                - v4: Always use iid (use_iid parameter ignored)
            use_iid: If True, treat mr_identifier as iid; if False, as global id (v3 only)

        Returns:
            Dict[str, Any]: MR data with fields:
            - v3: id, iid, state, merge_status, work_in_progress
            - v4: id, iid, state, has_conflicts, merge_status

        Example:
            # v4 or v3 with iid
            mr = gitlab_service.get_merge_request(
                project_id="wisedu-tech/api-designer",
                mr_identifier=42,
                use_iid=True
            )

            # v3 with global id
            mr = gitlab_service.get_merge_request(
                project_id="wisedu-tech/api-designer",
                mr_identifier=15083,
                use_iid=False
            )
        """
        try:
            project_id_encoded = project_id.replace("/", "%2F")

            # v3 API: GET /projects/:id/merge_request/:merge_request_id (note: singular "merge_request")
            # v4 API: GET /projects/:id/merge_requests/:merge_request_iid (note: plural "merge_requests")
            if self.base.api_version == "v3":
                if use_iid:
                    # v3 使用 iid 时，需要先列出所有 MR 然后过滤
                    # 这不太高效，但 v3 API 的设计就是这样
                    response = self.base.session.get(
                        self.base._get_api_url(f"projects/{project_id_encoded}/merge_requests"),
                        headers=self.base._get_headers(),
                        params={"iid": mr_identifier},
                        timeout=self.base._get_timeout(),
                    )
                    response.raise_for_status()
                    mrs = response.json()
                    if mrs and len(mrs) > 0:
                        return mrs[0]
                    else:
                        logger.warning(f"MR with iid={mr_identifier} not found in {project_id}")
                        return None
                else:
                    # v3 使用全局 ID（注意：使用单数 merge_request）
                    response = self.base.session.get(
                        self.base._get_api_url(f"projects/{project_id_encoded}/merge_request/{mr_identifier}"),
                        headers=self.base._get_headers(),
                        timeout=self.base._get_timeout(),
                    )
                    response.raise_for_status()
                    return response.json()
            else:  # v4
                # v4 always uses iid
                response = self.base.session.get(
                    self.base._get_api_url(f"projects/{project_id_encoded}/merge_requests/{mr_identifier}"),
                    headers=self.base._get_headers(),
                    timeout=self.base._get_timeout(),
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Failed to get MR {mr_identifier} in {project_id}: {e}")
            return None

    def can_merge(
        self, project_id: str, mr_identifier: int, max_retries: int = 5, retry_delay: float = 2.0
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a Merge Request can be merged

        如果 merge_status 为 'unchecked'，会自动重试等待 GitLab 完成检查

        Args:
            project_id: Project ID or namespace/project path
            mr_identifier: MR identifier (iid)
            max_retries: 最大重试次数（默认 5 次）
            retry_delay: 重试间隔秒数（默认 2 秒）

        Returns:
            tuple[bool, Optional[str]]: (can_merge, reason)
            - (True, None) - Can be merged
            - (False, "has_conflicts") - Has merge conflicts
            - (False, "work_in_progress") - MR is WIP
            - (False, "not_open") - MR is not in opened state
            - (False, "merge_status_unchecked") - GitLab still checking (after retries)
            - (False, "cannot_be_merged") - Other reasons

        Example:
            can_merge, reason = gitlab_service.can_merge("wisedu-tech/api-designer", 42)
            if can_merge:
                print("Can merge")
            else:
                print(f"Cannot merge: {reason}")
        """
        try:
            # 重试逻辑：等待 GitLab 完成 merge_status 检查
            for attempt in range(max_retries):
                mr_data = self.get_merge_request(project_id, mr_identifier)
                if not mr_data:
                    return False, "mr_not_found"

                # Check state
                state = mr_data.get("state", "")
                if state != "opened":
                    return False, "not_open"

                # Check WIP status
                if mr_data.get("work_in_progress", False):
                    return False, "work_in_progress"

                # Check merge status (v3/v4 compatible)
                if self.base.api_version == "v3":
                    # v3 uses merge_status field
                    merge_status = mr_data.get("merge_status", "")

                    if merge_status == "can_be_merged":
                        logger.info(f"MR #{mr_identifier} can be merged (attempt {attempt + 1}/{max_retries})")
                        return True, None
                    elif merge_status == "cannot_be_merged":
                        logger.warning(f"MR #{mr_identifier} has conflicts")
                        return False, "has_conflicts"
                    elif merge_status == "unchecked":
                        # GitLab 还在检查，需要等待
                        if attempt < max_retries - 1:
                            logger.info(
                                f"MR #{mr_identifier} merge status is 'unchecked', waiting... (attempt {attempt + 1}/{max_retries})"
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            # 已重试多次仍未检查完成
                            logger.warning(
                                f"MR #{mr_identifier} merge status still 'unchecked' after {max_retries} retries"
                            )
                            return False, "merge_status_unchecked"
                    else:
                        # 未知状态
                        logger.warning(f"MR #{mr_identifier} unknown merge_status: {merge_status}")
                        return False, f"unknown_status_{merge_status}"

                else:  # v4
                    # v4 has explicit has_conflicts field
                    has_conflicts = mr_data.get("has_conflicts", False)
                    if has_conflicts:
                        return False, "has_conflicts"

                    merge_status = mr_data.get("merge_status", "")
                    if merge_status == "can_be_merged":
                        return True, None
                    elif merge_status == "unchecked" or merge_status == "checking":
                        # GitLab 还在检查
                        if attempt < max_retries - 1:
                            logger.info(
                                f"MR #{mr_identifier} merge status is '{merge_status}', waiting... (attempt {attempt + 1}/{max_retries})"
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.warning(
                                f"MR #{mr_identifier} merge status still '{merge_status}' after {max_retries} retries"
                            )
                            return False, "merge_status_unchecked"
                    else:
                        return False, f"unknown_status_{merge_status}"

            # 如果循环结束还没返回，说明重试耗尽
            return False, "max_retries_exceeded"

        except Exception as e:
            logger.error(f"Failed to check merge status for MR {mr_identifier}: {e}")
            return False, "check_failed"

    def merge_merge_request(
        self,
        project_id: str,
        mr_identifier: int,
        merge_commit_message: Optional[str] = None,
        should_remove_source_branch: bool = False,
        use_iid: bool = True,
    ) -> MergeResult:
        """
        Merge a Merge Request (合并 MR)

        Args:
            project_id: Project ID or namespace/project path
            mr_identifier: MR identifier
                - v3: Can use iid (default) or global id
                - v4: Must use iid
            merge_commit_message: Custom merge commit message
            should_remove_source_branch: Remove source branch after merge
            use_iid: If True, treat mr_identifier as iid; if False, as global id (v3 only)

        Returns:
            MergeResult: 标准化的合并结果对象,包含:
                - success: 是否成功
                - status: 合并状态 ('merged' | 'conflict' | 'same_content' | 'already_merged' | 'failed')
                - mr_iid: MR IID
                - mr_state: MR 状态
                - merge_commit_sha: 合并提交 SHA (成功时)
                - error_message: 错误消息 (失败时)
                - mr_url: MR URL

        Example:
            result = gitlab_service.merge_merge_request(
                project_id="wisedu-tech/api-designer",
                mr_identifier=42,
                merge_commit_message="Merge feature branch to dev"
            )

            if result.success:
                print(f"Merged successfully: {result.merge_commit_sha}")
            elif result.status == 'conflict':
                print(f"Has conflicts, manual resolution needed")
            else:
                print(f"Merge failed: {result.error_message}")
        """
        # 生成 MR URL (提前生成,无论成功失败都需要)
        mr_url = self.get_merge_request_url(project_id, mr_identifier)

        try:
            project_id_encoded = project_id.replace("/", "%2F")

            data = {}
            if merge_commit_message:
                data["merge_commit_message"] = merge_commit_message
            if should_remove_source_branch:
                data["should_remove_source_branch"] = should_remove_source_branch

            # v3 API: PUT /projects/:id/merge_request/:merge_request_id/merge (singular, uses global ID or iid)
            # v4 API: PUT /projects/:id/merge_requests/:merge_request_iid/merge (plural, uses iid)
            if self.base.api_version == "v3":
                # v3 可以使用 iid 或全局 ID
                # 如果使用 iid,需要先获取 MR 得到全局 ID
                if use_iid:
                    mr_data = self.get_merge_request(project_id, mr_identifier, use_iid=True)
                    if not mr_data:
                        return MergeResult(
                            success=False,
                            status="failed",
                            mr_iid=mr_identifier,
                            mr_state=None,
                            merge_commit_sha=None,
                            error_message=f"MR #{mr_identifier} not found",
                            mr_url=mr_url,
                        )
                    global_id = mr_data.get("id")
                else:
                    global_id = mr_identifier

                # v3 使用单数 merge_request 和全局 ID
                response = self.base.session.put(
                    self.base._get_api_url(f"projects/{project_id_encoded}/merge_request/{global_id}/merge"),
                    headers=self.base._get_headers(),
                    json=data,
                    timeout=self.base._get_timeout(),
                )
            else:  # v4
                # v4 使用复数 merge_requests 和 iid
                response = self.base.session.put(
                    self.base._get_api_url(f"projects/{project_id_encoded}/merge_requests/{mr_identifier}/merge"),
                    headers=self.base._get_headers(),
                    json=data,
                    timeout=self.base._get_timeout(),
                )

            # ====================================================================
            # 处理响应 - 根据 HTTP 状态码判断合并结果
            # ====================================================================
            if response.status_code == 200:
                # 合并成功
                mr_data = response.json()
                merge_commit_sha = mr_data.get("merge_commit_sha") or mr_data.get("sha")
                logger.info(f"Successfully merged MR #{mr_identifier} in {project_id}, commit: {merge_commit_sha}")

                return MergeResult(
                    success=True,
                    status="merged",
                    mr_iid=mr_identifier,
                    mr_state=mr_data.get("state", "merged"),
                    merge_commit_sha=merge_commit_sha,
                    error_message=None,
                    mr_url=mr_url,
                )

            elif response.status_code == 405:
                # 无法合并 - 可能是冲突、已合并、源/目标分支相同、或无变更
                # 获取 MR 详情来判断具体原因
                mr_detail = self.get_merge_request(project_id, mr_identifier, use_iid=True)

                error_text = response.text
                logger.warning(f"MR #{mr_identifier} cannot be merged (405): {error_text}")

                # 优先检查错误信息中的关键词
                nothing_to_merge_keywords = [
                    "nothing to merge",
                    "no commits between",
                    "there are no commits",
                    "source and target branches are the same",
                ]

                error_text_lower = error_text.lower()
                is_nothing_to_merge = any(keyword in error_text_lower for keyword in nothing_to_merge_keywords)

                if is_nothing_to_merge:
                    # 分支内容完全一致，无需合并（通过错误信息判断）
                    logger.info(f"MR #{mr_identifier} has no changes to merge (405, keyword match)")
                    return MergeResult(
                        success=False,
                        status="same_content",
                        mr_iid=mr_identifier,
                        mr_state=mr_detail.get("state") if mr_detail else "opened",
                        merge_commit_sha=None,
                        error_message="源分支和目标分支内容一致，无需合并",
                        mr_url=mr_url,
                    )

                if mr_detail:
                    mr_state = mr_detail.get("state", "")
                    merge_status = mr_detail.get("merge_status", "")

                    # 检查 MR 状态 - 如果已经是 merged/closed,说明已经合并或关闭
                    if mr_state in ["merged", "closed"]:
                        return MergeResult(
                            success=False,
                            status="already_merged",
                            mr_iid=mr_identifier,
                            mr_state=mr_state,
                            merge_commit_sha=mr_detail.get("merge_commit_sha"),
                            error_message=f"MR 已经{mr_state}",
                            mr_url=mr_url,
                        )

                    # 关键判断：MR 是 opened 状态，但 405 错误 + merge_status 不是 cannot_be_merged
                    # 这种情况很可能是"无需合并"（分支内容一致）
                    # GitLab v3 API 在这种情况下只返回简单的 "405 Method Not Allowed"
                    if mr_state == "opened" and merge_status != "cannot_be_merged":
                        logger.info(
                            f"MR #{mr_identifier} likely has no changes (405, opened state, merge_status={merge_status})"
                        )
                        logger.debug(f"MR detail: state={mr_state}, merge_status={merge_status}")
                        return MergeResult(
                            success=False,
                            status="same_content",
                            mr_iid=mr_identifier,
                            mr_state=mr_state,
                            merge_commit_sha=None,
                            error_message="源分支和目标分支内容一致，无需合并",
                            mr_url=mr_url,
                        )

                    # MR 仍然是 opened 状态,检查 merge_status
                    if merge_status == "cannot_be_merged":
                        # 明确标记为无法合并 - 有冲突
                        return MergeResult(
                            success=False,
                            status="conflict",
                            mr_iid=mr_identifier,
                            mr_state=mr_state,
                            merge_commit_sha=None,
                            error_message="MR 存在冲突,无法自动合并",
                            mr_url=mr_url,
                        )

                # 默认当作冲突处理
                logger.warning(f"MR #{mr_identifier} merge failed with 405, treating as conflict")
                return MergeResult(
                    success=False,
                    status="conflict",
                    mr_iid=mr_identifier,
                    mr_state=mr_detail.get("state") if mr_detail else None,
                    merge_commit_sha=None,
                    error_message=f"MR 无法合并: {error_text}",
                    mr_url=mr_url,
                )

            elif response.status_code == 406:
                # 406 可能表示多种情况：已合并、已关闭、有冲突、或无变更
                # 需要检查 MR 详情来判断具体原因
                error_text = response.text
                logger.warning(f"MR #{mr_identifier} cannot be merged (406): {error_text}")

                # 优先检查错误信息中的关键词
                nothing_to_merge_keywords = [
                    "nothing to merge",
                    "no commits between",
                    "there are no commits",
                    "source and target branches are the same",
                ]

                error_text_lower = error_text.lower()
                is_nothing_to_merge = any(keyword in error_text_lower for keyword in nothing_to_merge_keywords)

                if is_nothing_to_merge:
                    # 分支内容完全一致，无需合并（通过错误信息判断）
                    logger.info(f"MR #{mr_identifier} has no changes to merge (406, keyword match)")
                    mr_detail = self.get_merge_request(project_id, mr_identifier, use_iid=True)
                    return MergeResult(
                        success=False,
                        status="same_content",
                        mr_iid=mr_identifier,
                        mr_state=mr_detail.get("state") if mr_detail else "opened",
                        merge_commit_sha=None,
                        error_message="源分支和目标分支内容一致，无需合并",
                        mr_url=mr_url,
                    )

                mr_detail = self.get_merge_request(project_id, mr_identifier, use_iid=True)

                if mr_detail:
                    mr_state = mr_detail.get("state", "")
                    merge_status = mr_detail.get("merge_status", "")

                    # 检查 MR 状态
                    if mr_state == "merged":
                        # 真的是已经合并
                        logger.info(f"MR #{mr_identifier} is already merged")
                        return MergeResult(
                            success=False,
                            status="already_merged",
                            mr_iid=mr_identifier,
                            mr_state=mr_state,
                            merge_commit_sha=mr_detail.get("merge_commit_sha"),
                            error_message="MR 已经合并",
                            mr_url=mr_url,
                        )
                    elif mr_state == "closed":
                        # MR 已关闭
                        logger.info(f"MR #{mr_identifier} is closed")
                        return MergeResult(
                            success=False,
                            status="already_merged",
                            mr_iid=mr_identifier,
                            mr_state=mr_state,
                            merge_commit_sha=None,
                            error_message="MR 已关闭",
                            mr_url=mr_url,
                        )

                    # 关键判断：MR 是 opened 状态，但 406 错误 + merge_status 不是 cannot_be_merged
                    # 且错误信息中不包含 "conflict" 关键词
                    # 这种情况很可能是"无需合并"（分支内容一致）
                    if (
                        mr_state == "opened"
                        and merge_status != "cannot_be_merged"
                        and "conflict" not in error_text.lower()
                    ):
                        logger.info(
                            f"MR #{mr_identifier} likely has no changes (406, opened state, merge_status={merge_status})"
                        )
                        logger.debug(f"MR detail: state={mr_state}, merge_status={merge_status}")
                        return MergeResult(
                            success=False,
                            status="same_content",
                            mr_iid=mr_identifier,
                            mr_state=mr_state,
                            merge_commit_sha=None,
                            error_message="源分支和目标分支内容一致，无需合并",
                            mr_url=mr_url,
                        )

                    # 明确的冲突判断
                    if merge_status == "cannot_be_merged" or "conflict" in error_text.lower():
                        # MR 有冲突（opened 状态但无法合并）
                        logger.warning(f"MR #{mr_identifier} has conflicts (406)")
                        return MergeResult(
                            success=False,
                            status="conflict",
                            mr_iid=mr_identifier,
                            mr_state=mr_state,
                            merge_commit_sha=None,
                            error_message="MR 存在冲突,无法自动合并",
                            mr_url=mr_url,
                        )

                # 默认处理：无法合并
                logger.warning(f"MR #{mr_identifier} merge failed with 406, treating as conflict")
                return MergeResult(
                    success=False,
                    status="conflict",
                    mr_iid=mr_identifier,
                    mr_state=mr_detail.get("state") if mr_detail else None,
                    merge_commit_sha=None,
                    error_message=f"MR 无法合并: {error_text}",
                    mr_url=mr_url,
                )

            else:
                # 其他 HTTP 错误
                error_text = response.text
                logger.error(f"Failed to merge MR #{mr_identifier}: HTTP {response.status_code}, {error_text}")

                return MergeResult(
                    success=False,
                    status="failed",
                    mr_iid=mr_identifier,
                    mr_state=None,
                    merge_commit_sha=None,
                    error_message=f"HTTP {response.status_code}: {error_text}",
                    mr_url=mr_url,
                )

        except requests.RequestException as e:
            # 网络错误
            logger.error(f"Network error while merging MR #{mr_identifier}: {e}")
            return MergeResult(
                success=False,
                status="failed",
                mr_iid=mr_identifier,
                mr_state=None,
                merge_commit_sha=None,
                error_message=f"网络错误: {str(e)}",
                mr_url=mr_url,
            )

        except Exception as e:
            # 其他异常
            logger.error(f"Unexpected error while merging MR #{mr_identifier}: {e}")
            return MergeResult(
                success=False,
                status="failed",
                mr_iid=mr_identifier,
                mr_state=None,
                merge_commit_sha=None,
                error_message=f"未知错误: {str(e)}",
                mr_url=mr_url,
            )

    def get_merge_request_url(self, project_id: str, mr_iid: int) -> str:
        """
        Generate Merge Request web URL

        Args:
            project_id: Project ID or namespace/project path
            mr_iid: MR IID (project-scoped ID)

        Returns:
            str: Full URL to the MR in GitLab web interface
            Format: {gitlab_url}/{project_id}/merge_requests/{mr_iid}

        Example:
            url = gitlab_service.get_merge_request_url("wisedu-tech/api-designer", 42)
            # Returns: http://172.16.7.53:9090/wisedu-tech/api-designer/merge_requests/42
        """
        gitlab_url = module_config_service.get_gitlab_url()

        # GitLab v3/v4 use same URL format for MR web interface
        mr_url = f"{gitlab_url}/{project_id}/merge_requests/{mr_iid}"

        return mr_url

    def close_merge_request(
        self, project_id: str, mr_identifier: int, state_event: str = "close", use_iid: bool = True
    ) -> bool:
        """
        关闭 Merge Request

        当MR无需处理时（如分支内容一致），自动关闭MR避免开发者手动处理。

        Args:
            project_id: 项目ID或命名空间/项目路径
            mr_identifier: MR的IID（项目范围内的ID）
            state_event: 状态事件，默认 "close"（也可以是 "reopen"）
            use_iid: 是否使用 iid（v3 可以用全局 ID，v4 必须用 iid）

        Returns:
            bool: 是否成功关闭

        Example:
            success = gitlab_service.close_merge_request("zhuguidong/demo-git", 21)
        """
        try:
            project_id_encoded = project_id.replace("/", "%2F")
            data = {"state_event": state_event}

            # v3 API: PUT /projects/:id/merge_request/:merge_request_id (singular, uses global ID or iid)
            # v4 API: PUT /projects/:id/merge_requests/:merge_request_iid (plural, uses iid)
            if self.base.api_version == "v3":
                # v3 可以使用 iid 或全局 ID
                if use_iid:
                    # 先获取 MR 得到全局 ID
                    mr_data = self.get_merge_request(project_id, mr_identifier, use_iid=True)
                    if not mr_data:
                        logger.warning(f"MR #{mr_identifier} not found in {project_id}")
                        return False
                    global_id = mr_data.get("id")
                else:
                    global_id = mr_identifier

                # v3 使用单数 merge_request 和全局 ID
                response = self.base.session.put(
                    self.base._get_api_url(f"projects/{project_id_encoded}/merge_request/{global_id}"),
                    headers=self.base._get_headers(),
                    json=data,
                    timeout=self.base._get_timeout(),
                )
            else:  # v4
                # v4 使用复数 merge_requests 和 iid
                response = self.base.session.put(
                    self.base._get_api_url(f"projects/{project_id_encoded}/merge_requests/{mr_identifier}"),
                    headers=self.base._get_headers(),
                    json=data,
                    timeout=self.base._get_timeout(),
                )

            if response.status_code == 200:
                mr_data = response.json()
                new_state = mr_data.get("state", "unknown")
                logger.info(f"Successfully closed MR #{mr_identifier}, current state: {new_state}")
                return True
            else:
                logger.warning(f"Failed to close MR #{mr_identifier}: {response.status_code} - {response.text}")
                return False

        except requests.RequestException as e:
            logger.error(f"Network error while closing MR #{mr_identifier}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unknown error while closing MR #{mr_identifier}: {e}")
            return False
