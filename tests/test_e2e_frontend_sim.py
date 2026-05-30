"""End-to-end simulation: a frontend card from Jira (over MCP) to a draft PR
with a screenshot, proving the whole pipeline wires together.

CI-safe: the worktree/git/PR boundaries are faked and the screenshot capturer is
injected (a real, tiny PNG), so no browser, network or live tenant is needed.
The *frontend edit* is real — the fake executor rewrites ``index.html`` exactly
as simplicio-cli would apply a diff — and the screenshot artifact is a real PNG
file committed under ``.sendsprint/evidence/``.
"""

from __future__ import annotations

import base64
import sys

import pytest

from sendsprint import flow as flow_mod
from sendsprint.delivery import evidence as evidence_mod
from sendsprint.delivery.pr import PullRequestManager
from sendsprint.flow import RepoTarget, SprintFlow
from sendsprint.models.reports import PrInfo, StepReport, TestEvidence
from sendsprint.operators import _mcp_bridge
from sendsprint.operators.jira_operator import JiraOperator

# A real 1x1 PNG — stands in for the Playwright capture in CI.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

INDEX_BEFORE = "<html><body><header><h1>Acme</h1></header></body></html>"


def _frontend_card_payload() -> dict:
    return {
        "sprint": {"id": "42", "name": "Sprint 42 — Auth UI", "state": "active"},
        "issues": [
            {
                "id": "9001",
                "key": "WEB-7",
                "fields": {
                    "summary": "Add a Login button to the homepage header",
                    "description": "The header has no way to sign in.",
                    "issuetype": {"name": "Story"},
                    "status": {"name": "To Do"},
                    "assignee": {"displayName": "Wesley", "emailAddress": "me@x.com"},
                    "customfield_10100": (
                        "- Header shows a 'Login' button\n- Button links to /login"
                    ),
                },
            }
        ],
    }


class FakeWorktree:
    def __init__(self, repo_path):  # noqa: ANN001
        self.repo = repo_path

    def create(self, branch, base="HEAD"):  # noqa: ANN001
        return self.repo

    def remove(self, branch):  # noqa: ANN001
        pass

    def worktree_dir(self, branch):  # noqa: ANN001
        return self.repo


class FrontendExecutor:
    """Simulate simplicio applying a diff: add the Login button to index.html."""

    def __init__(self, work_dir, **kw):  # noqa: ANN001
        self.work_dir = work_dir

    def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
        index = self.work_dir / "index.html"
        html = index.read_text()
        html = html.replace("</header>", '<a href="/login"><button>Login</button></a></header>')
        index.write_text(html)
        return StepReport(step=3, name=f"execute:{item.key}", status="ok", message="diff applied")


class FakeGit:
    def __init__(self, work_dir, **kw):  # noqa: ANN001
        self.pushed: list[str] = []

    def commit_all(self, message):  # noqa: ANN001
        return True

    def push(self, branch=None, **kw):  # noqa: ANN001
        self.pushed.append(branch)


class RecordingPR:
    last = None

    def __init__(self, provider, repo, **kw):  # noqa: ANN001
        self.repo = repo
        self.evidence: list[TestEvidence] = []
        RecordingPR.last = self

    def create_pr(self, *, title, body, head, base, draft):  # noqa: ANN001
        return PrInfo(
            provider="github",
            repo=self.repo,
            number=77,
            url=f"https://github.com/{self.repo}/pull/77",
            title=title,
            source_branch=head,
            target_branch=base,
            state="draft" if draft else "open",
        )

    def post_evidence(  # noqa: ANN001
        self, pr_number, *, branch, evidence, steps_completed=None, review_feedback=None
    ):
        self.evidence = evidence


@pytest.fixture(autouse=True)
def _clear_providers():
    _mcp_bridge.clear_providers()
    yield
    _mcp_bridge.clear_providers()


def test_frontend_card_to_pr_with_screenshot(tmp_path, monkeypatch):
    # 1) Receive the task from Jira over MCP (host-injected provider).
    _mcp_bridge.register_provider("jira", lambda **q: _frontend_card_payload())
    operator = JiraOperator(base_url="https://x.atlassian.net", email="me@x.com", api_token="t")
    sprint = operator.read_sprint(sprint_id="42")
    assert sprint.transport == "mcp"
    card = sprint.items[0]
    assert card.key == "WEB-7"
    assert "Login" in card.acceptance_criteria

    # 2) A repo with a frontend that lacks the button yet.
    (tmp_path / "index.html").write_text(INDEX_BEFORE)

    # Fake the boundaries; capture a real PNG instead of launching a browser.
    monkeypatch.setattr(flow_mod, "WorktreeManager", FakeWorktree)
    monkeypatch.setattr(flow_mod, "SimplicioExecutor", FrontendExecutor)
    monkeypatch.setattr(flow_mod, "GitOps", FakeGit)
    monkeypatch.setattr(flow_mod, "PullRequestManager", RecordingPR)
    monkeypatch.setattr(
        flow_mod, "detect_tech", lambda p: type("T", (), {"primary_tech": "html"})()
    )

    def fake_capture(url, out_path):  # noqa: ANN001
        from pathlib import Path

        Path(out_path).write_bytes(_PNG_1X1)
        return True

    monkeypatch.setattr(evidence_mod, "_playwright_screenshot", fake_capture)

    target = RepoTarget(
        path=tmp_path,
        name="acme/web",
        repo_slug="acme/web",
        tech="html",
        test_command=f'"{sys.executable}" -c "pass"',  # passes cross-platform
        base_branch="develop",
        pr_provider="github",
        frontend_url=f"file://{tmp_path}/index.html",
    )
    flow = SprintFlow(operator, target, draft_prs=True)

    # 3) Run the flow end to end for the card.
    outcome = flow.deliver_item(card, sprint=sprint, index=1)

    names = {s.name.split(":")[0]: s for s in outcome.steps}
    assert names["mapper"].status == "ok"
    assert names["execute"].status == "ok"
    assert names["evidence"].status == "ok"
    assert names["commit"].status == "ok"
    assert names["pr"].status == "ok"

    # 4) The frontend was really edited.
    assert "Login</button>" in (tmp_path / "index.html").read_text()

    # 5) The mapper spec was written with the acceptance criteria.
    specs = list(tmp_path.glob(".specs/sprints/*/*.task.md"))
    assert specs and "Login" in specs[0].read_text()

    # 6) A real screenshot artifact exists and is a PNG, attached to the PR.
    shot = tmp_path / ".sendsprint/evidence/WEB-7/screen.png"
    assert shot.exists() and shot.read_bytes().startswith(b"\x89PNG")
    screenshots = [e for e in RecordingPR.last.evidence if e.kind == "screenshot"]
    assert screenshots and screenshots[0].passed

    # 7) The draft PR was opened.
    assert outcome.pr is not None and outcome.pr.state == "draft"


def test_pr_body_embeds_screenshot_image():
    mgr = PullRequestManager("github", "acme/web")
    evidence = [
        TestEvidence(kind="unit", title="pytest", passed=True, message="exit 0"),
        TestEvidence(
            kind="screenshot",
            title="homepage",
            passed=True,
            path="/w/.sendsprint/evidence/WEB-7/screen.png",
        ),
    ]
    body = mgr._render_evidence("feature/web-7", evidence, ["execute", "evidence", "commit"])
    assert "✅ **unit**" in body
    assert (
        "![homepage](https://raw.githubusercontent.com/acme/web/feature/web-7/"
        ".sendsprint/evidence/WEB-7/screen.png)" in body
    )
