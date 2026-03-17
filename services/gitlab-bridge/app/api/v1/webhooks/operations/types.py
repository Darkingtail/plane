"""
Webhook operation type definitions

Uses TypedDict for internal data structures with type hints and IDE support.
"""

from typing import List, NotRequired, TypedDict


class MergeResultItem(TypedDict, total=False):
    """
    Single module merge result

    Returned by merge_feature_to_branch(), used in:
    - integrating.py: integration workflow
    - testing.py: testing workflow
    - comment.py: generate Plane comments

    Fields:
        module: Module name (required)
        success: Whether merge succeeded (required)
        branch_name: Source branch name
        target_branch: Target branch name
        commit_sha: Merge commit SHA (on success)
        mr_url: Merge Request URL
        error: Error message (on failure)
        skip_reason: Skip reason, e.g. "same_content" (when no merge needed)
        mr_closed: Whether MR was auto-closed (when no merge needed)
        status: Special status, e.g. "conflict" (on conflict)
    """

    # Required fields
    module: str
    success: bool

    # Optional fields
    branch_name: NotRequired[str]
    target_branch: NotRequired[str]
    commit_sha: NotRequired[str]
    mr_url: NotRequired[str]
    error: NotRequired[str]
    skip_reason: NotRequired[str]
    mr_closed: NotRequired[bool]
    status: NotRequired[str]


# Type alias
MergeResultList = List[MergeResultItem]
