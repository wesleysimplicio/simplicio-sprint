"""Worktree and file-pattern lock primitives for parallel delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from fnmatch import fnmatch
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LockKind = Literal["repo", "worktree", "issue", "files"]


class LockClaim(BaseModel):
    """One ownership claim over a mutable delivery scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    owner: str
    repo: str
    kind: LockKind
    key: str
    file_patterns: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def conflicts_with(self, other: LockClaim) -> bool:
        if self.repo != other.repo:
            return False
        if self.kind in {"repo", "worktree", "issue"} and self.kind == other.kind:
            return self.key == other.key
        if self.kind == "files" and other.kind == "files":
            return _patterns_overlap(self.file_patterns, other.file_patterns)
        if self.kind == "files":
            return any(fnmatch(other.key, pattern) for pattern in self.file_patterns)
        if other.kind == "files":
            return any(fnmatch(self.key, pattern) for pattern in other.file_patterns)
        return False


class LockRegistry(BaseModel):
    """In-memory lock registry with explicit conflict checking."""

    model_config = ConfigDict(extra="forbid")

    claims: list[LockClaim] = Field(default_factory=list)

    def acquire(self, claim: LockClaim) -> None:
        for current in self.claims:
            if current.owner != claim.owner and current.conflicts_with(claim):
                raise ValueError(
                    f"lock conflict: {current.owner} already owns {current.kind}:{current.key}"
                )
        self.claims.append(claim)

    def release_owner(self, owner: str) -> None:
        self.claims = [claim for claim in self.claims if claim.owner != owner]


def _patterns_overlap(left: list[str], right: list[str]) -> bool:
    for pattern in left:
        for candidate in right:
            if pattern == candidate:
                return True
            if fnmatch(candidate, pattern) or fnmatch(pattern, candidate):
                return True
    return False
