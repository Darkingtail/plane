"""
GitLab API Response Models
"""

from typing import Optional

from pydantic import BaseModel, Field


class MergeResult(BaseModel):
    """
    GitLab Merge Request 合并结果

    用于标准化 MR 合并操作的返回值,便于调用方判断合并成功/失败原因
    """

    success: bool = Field(..., description="合并是否成功")

    status: str = Field(
        ...,
        description=(
            "合并状态:\n"
            "- 'merged': 成功合并\n"
            "- 'conflict': 存在冲突,无法自动合并\n"
            "- 'same_content': 源分支和目标分支内容相同,无需合并\n"
            "- 'already_merged': MR 已经合并或已关闭\n"
            "- 'failed': 其他错误"
        ),
    )

    mr_iid: int = Field(..., description="MR IID (项目内唯一标识)")

    mr_state: Optional[str] = Field(None, description="MR 状态: 'merged' | 'opened' | 'closed'")

    merge_commit_sha: Optional[str] = Field(None, description="合并提交的 SHA (仅成功时有值)")

    error_message: Optional[str] = Field(None, description="错误消息 (仅失败时有值)")

    mr_url: str = Field(..., description="MR 的 GitLab Web URL")
