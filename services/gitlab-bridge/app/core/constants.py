"""
Application constants
"""

from enum import Enum
from pathlib import Path


# 项目根目录（services/gitlab-bridge/）
BASE_DIR = Path(__file__).parent.parent.parent


class Environment(str, Enum):
    """部署环境枚举"""

    DEV = "dev"
    TEST = "test"
    RELEASE = "release"
    PRODUCTION = "production"


# 评论模板常量（HTML 格式，适配 Plane comment_html）
COMMENT_TITLE_FREEZE_START = "开始封版"
COMMENT_TITLE_FREEZE_EXECUTE = "执行封版"
COMMENT_TITLE_FREEZE_COMPLETE = "封版完成"
COMMENT_TITLE_RELEASE_AUTO = "发布完成（联动Git发版）"
COMMENT_TITLE_RELEASE_MANUAL = "发布完成（手动模式）"

COMMENT_MARKER_STORY_LIST_START = "待发版 Issue 列表"
COMMENT_MARKER_STORY_LIST_EXECUTE = "涉及的 Issue"
COMMENT_MARKER_REPOSITORY_LIST = "涉及的仓库"
