"""Open-source contributor mode helpers."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class OssContributorMode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    has_contributing: bool = False
    has_code_of_conduct: bool = False
    has_security: bool = False
    has_pr_template: bool = False
    prefer_fork_workflow: bool = True


def detect_oss_mode(repo_path: str | Path) -> OssContributorMode:
    root = Path(repo_path)
    return OssContributorMode(
        has_contributing=(root / "CONTRIBUTING.md").is_file(),
        has_code_of_conduct=(root / "CODE_OF_CONDUCT.md").is_file(),
        has_security=(root / "SECURITY.md").is_file(),
        has_pr_template=(root / ".github" / "PULL_REQUEST_TEMPLATE.md").is_file(),
        prefer_fork_workflow=True,
    )
