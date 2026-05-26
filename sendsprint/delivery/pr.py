"""Pull request creation, evidence posting and review-feedback reading.

GitHub PRs are created via the REST API as drafts (the human approval gate is
the user's only touchpoint). Evidence — test results plus screenshots committed
on the branch — is posted as a comment with the images embedded by raw URL.
Review feedback is read back through :class:`ReviewReader` to feed the
simplicio revise loop.
"""

from __future__ import annotations

import base64
import logging
import os
from collections.abc import Callable

import httpx

from sendsprint.github_integration import ProgressReporter, ReviewFeedback, ReviewReader
from sendsprint.models.reports import PrInfo, TestEvidence

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
EVIDENCE_PREFIX = ".sendsprint/evidence/"


class PullRequestManager:
    """Open PRs and manage the evidence + review surface for one repo."""

    def __init__(
        self,
        provider: str,
        repo: str,
        *,
        token: str | None = None,
        # Azure DevOps context (only used when provider == "azuredevops").
        organization: str | None = None,
        project: str | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.provider = provider
        self.repo = repo
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.organization = organization or os.getenv("AZURE_DEVOPS_ORG", "")
        self.project = project or os.getenv("AZURE_DEVOPS_PROJECT", "")
        self._pat = os.getenv("AZURE_DEVOPS_PAT", "")
        self._client_factory = client_factory

    # -- PR creation --------------------------------------------------------

    def create_pr(
        self,
        *,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = True,
    ) -> PrInfo:
        if self.provider == "github":
            return self._create_github_pr(title=title, body=body, head=head, base=base, draft=draft)
        if self.provider == "azuredevops":
            return self._create_ado_pr(title=title, body=body, head=head, base=base, draft=draft)
        raise ValueError(f"unknown PR provider: {self.provider}")

    def _create_github_pr(
        self, *, title: str, body: str, head: str, base: str, draft: bool
    ) -> PrInfo:
        payload = {"title": title, "head": head, "base": base, "body": body, "draft": draft}
        with self._github_client() as client:
            resp = client.post(f"{GITHUB_API}/repos/{self.repo}/pulls", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return PrInfo(
            provider="github",
            repo=self.repo,
            number=data.get("number"),
            url=data.get("html_url"),
            title=title,
            body=body,
            source_branch=head,
            target_branch=base,
            state="draft" if draft else "open",
        )

    def _create_ado_pr(self, *, title: str, body: str, head: str, base: str, draft: bool) -> PrInfo:
        token = base64.b64encode(f":{self._pat}".encode()).decode()
        url = (
            f"https://dev.azure.com/{self.organization}/{self.project}"
            f"/_apis/git/repositories/{self.repo}/pullrequests?api-version=7.1"
        )
        payload = {
            "sourceRefName": f"refs/heads/{head}",
            "targetRefName": f"refs/heads/{base}",
            "title": title,
            "description": body,
            "isDraft": draft,
        }
        with httpx.Client(timeout=30.0, headers={"Authorization": f"Basic {token}"}) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        pr_id = data.get("pullRequestId")
        web_url = (
            f"https://dev.azure.com/{self.organization}/{self.project}"
            f"/_git/{self.repo}/pullrequest/{pr_id}"
            if pr_id
            else None
        )
        return PrInfo(
            provider="azuredevops",
            repo=self.repo,
            number=pr_id,
            url=web_url,
            title=title,
            body=body,
            source_branch=head,
            target_branch=base,
            state="draft" if draft else "open",
        )

    # -- Evidence + review (GitHub) ----------------------------------------

    def post_evidence(
        self,
        pr_number: int,
        *,
        branch: str,
        evidence: list[TestEvidence],
        steps_completed: list[str] | None = None,
    ) -> None:
        """Comment on the PR with test results + embedded screenshots."""
        if self.provider != "github":
            return
        body = self._render_evidence(branch, evidence, steps_completed)
        reporter = ProgressReporter(self.repo, token=self.token)
        reporter.post_progress_comment(pr_number, body)

    def read_feedback(self, pr_number: int) -> list[ReviewFeedback]:
        """Read actionable review feedback (CHANGES_REQUESTED + inline comments)."""
        if self.provider != "github":
            return []
        reader = ReviewReader(self.repo, token=self.token)
        return reader.extract_actionable_feedback(pr_number)

    def _render_evidence(
        self,
        branch: str,
        evidence: list[TestEvidence],
        steps_completed: list[str] | None,
    ) -> str:
        lines = ["## SendSprint evidence", ""]
        if steps_completed:
            lines.append("### Steps")
            lines += [f"- [x] {s}" for s in steps_completed]
            lines.append("")
        lines.append("### Tests & screens")
        for ev in evidence:
            mark = "✅" if ev.passed else "❌"
            detail = f" — {ev.message}" if ev.message else ""
            lines.append(f"- {mark} **{ev.kind}**: {ev.title}{detail}")
            if ev.kind == "screenshot" and ev.passed and ev.path:
                raw = self._raw_url(branch, ev.path)
                if raw:
                    lines.append("")
                    lines.append(f"  ![{ev.title}]({raw})")
                    lines.append("")
        return "\n".join(lines)

    def _raw_url(self, branch: str, path: str) -> str | None:
        """Build a raw.githubusercontent URL for a committed evidence artifact."""
        idx = path.find(EVIDENCE_PREFIX)
        if idx == -1:
            return None
        rel = path[idx:]
        return f"https://raw.githubusercontent.com/{self.repo}/{branch}/{rel}"

    # -- internals ----------------------------------------------------------

    def _github_client(self) -> httpx.Client:
        if self._client_factory is not None:
            return self._client_factory()
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return httpx.Client(timeout=30.0, headers=headers)
