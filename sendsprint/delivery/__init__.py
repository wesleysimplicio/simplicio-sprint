"""Delivery layer: worktree isolation, commits, evidence, pull requests.

SendSprint owns this whole layer. simplicio-cli only edits the working tree;
everything here — branching, committing, capturing evidence, opening the PR and
driving the review loop — is the agent's job.
"""

from sendsprint.delivery.evidence import EvidenceCollector
from sendsprint.delivery.git_ops import GitError, GitOps
from sendsprint.delivery.pr import PullRequestManager
from sendsprint.delivery.worktree import WorktreeError, WorktreeManager

__all__ = [
    "EvidenceCollector",
    "GitError",
    "GitOps",
    "PullRequestManager",
    "WorktreeError",
    "WorktreeManager",
]
