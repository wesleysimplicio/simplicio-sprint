"""PrCreator: creates PRs on GitHub (gh CLI) or Azure DevOps (REST)."""

from __future__ import annotations

import base64
import contextlib
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..models.reports import PrInfo, StepReport

logger = logging.getLogger(__name__)


class PrCreator:
    """Step 9: create a pull request after dev + test + security pass."""

    def __init__(
        self,
        repo_path: str | Path,
        *,
        provider: str = "github",
        target_branch: str = "main",
        reviewers: list[str] | None = None,
    ) -> None:
        self.repo = Path(repo_path).resolve()
        self.provider = provider
        self.target_branch = target_branch
        self.reviewers = reviewers or []

    def create(
        self,
        source_branch: str,
        title: str,
        body: str = "",
    ) -> StepReport:
        report = StepReport(step=9, name="create-pr", repo=str(self.repo))
        report.started_at = datetime.now(tz=UTC)
        report.status = "running"
        try:
            if self.provider == "github":
                pr = self._create_github(source_branch, title, body)
            elif self.provider == "azuredevops":
                pr = self._create_ado(source_branch, title, body)
            else:
                report.status = "failed"
                report.message = f"unknown provider: {self.provider}"
                return report
            report.pr = pr
            report.status = "ok"
            report.message = f"PR created: {pr.url or pr.number}"
        except Exception as exc:
            report.status = "failed"
            report.message = str(exc)[:2000]
        report.finished_at = datetime.now(tz=UTC)
        return report

    def _create_github(self, source: str, title: str, body: str) -> PrInfo:
        cmd = [
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--base",
            self.target_branch,
            "--head",
            source,
        ]
        for r in self.reviewers:
            cmd.extend(["--reviewer", r])
        result = subprocess.run(
            cmd,
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gh pr create failed: {result.stderr}")
        url = result.stdout.strip()
        number = None
        if "/" in url:
            with contextlib.suppress(ValueError):
                number = int(url.rstrip("/").rsplit("/", 1)[-1])
        repo_slug = self._gh_repo_slug()
        return PrInfo(
            provider="github",
            repo=repo_slug,
            number=number,
            url=url,
            title=title,
            body=body,
            source_branch=source,
            target_branch=self.target_branch,
            state="open",
        )

    def _create_ado(self, source: str, title: str, body: str) -> PrInfo:
        org = os.getenv("AZURE_DEVOPS_ORG", "")
        project = os.getenv("AZURE_DEVOPS_PROJECT", "")
        repo_name = os.getenv("AZURE_DEVOPS_REPO", self.repo.name)
        pat = os.getenv("AZURE_DEVOPS_PAT", "")
        if not (org and project and pat):
            raise RuntimeError("AZURE_DEVOPS_ORG/PROJECT/PAT required")
        token = base64.b64encode(f":{pat}".encode()).decode()
        url = (
            f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/"
            f"{repo_name}/pullrequests?api-version=7.1"
        )
        payload: dict[str, Any] = {
            "sourceRefName": f"refs/heads/{source}",
            "targetRefName": f"refs/heads/{self.target_branch}",
            "title": title,
            "description": body,
        }
        if self.reviewers:
            payload["reviewers"] = [{"uniqueName": r} for r in self.reviewers]
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Basic {token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        pr_id = data.get("pullRequestId")
        pr_url = f"https://dev.azure.com/{org}/{project}/_git/{repo_name}/pullrequest/{pr_id}"
        return PrInfo(
            provider="azuredevops",
            repo=f"{org}/{project}/{repo_name}",
            number=pr_id,
            url=pr_url,
            title=title,
            body=body,
            source_branch=source,
            target_branch=self.target_branch,
            state="open",
        )

    def _gh_repo_slug(self) -> str:
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return self.repo.name
