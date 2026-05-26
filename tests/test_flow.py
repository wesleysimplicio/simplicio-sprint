"""Integration test for the SprintFlow orchestrator with faked components."""

from __future__ import annotations

import pytest

from sendsprint import flow as flow_mod
from sendsprint.flow import RepoTarget, SprintFlow
from sendsprint.models.reports import PrInfo, StepReport, TestEvidence
from sendsprint.models.sprint import Sprint, SprintItem


class FakeOperator:
    source = "github"

    def __init__(self, items):
        self._items = items
        self.status_calls: list[tuple[str, str, str | None]] = []

    def read_sprint(self, **kwargs):  # noqa: ANN003
        return Sprint(id="s1", name="Sprint 1", source="github", items=self._items)

    def update_status(self, key, status, comment=None):  # noqa: ANN001
        self.status_calls.append((key, status, comment))

    def current_user(self):
        return {"emailAddress": "me@x.com"}


class FakeWorktree:
    def __init__(self, repo_path):
        self.repo = repo_path
        self.removed: list[str] = []

    def create(self, branch, base="HEAD"):  # noqa: ANN001
        return self.repo

    def remove(self, branch):  # noqa: ANN001
        self.removed.append(branch)

    def worktree_dir(self, branch):  # noqa: ANN001
        return self.repo


class FakeExecutor:
    def __init__(self, work_dir, **kw):  # noqa: ANN001
        self.work_dir = work_dir

    def run_item(self, item, *, stack=None, target=None, repo=None):  # noqa: ANN001
        return StepReport(step=3, name=f"execute:{item.key}", status="ok", message="ok")

    def revise(self, feedback, *, stack=None, target=None, repo=None):  # noqa: ANN001
        return StepReport(step=3, name="revise:pr-feedback", status="ok")


class FakeEvidence:
    def __init__(self, work_dir, *, item_key, **kw):  # noqa: ANN001
        pass

    def collect_tests(self, cmd):  # noqa: ANN001
        return TestEvidence(kind="unit", title=cmd or "tests", passed=True, message="exit 0")

    def capture_screenshot(self, url, *, name="screen", screenshot_fn=None):  # noqa: ANN001
        return None


class FakeGit:
    def __init__(self, work_dir, **kw):  # noqa: ANN001
        self.pushed: list[str] = []

    def commit_all(self, message):  # noqa: ANN001
        return True

    def push(self, branch=None, **kw):  # noqa: ANN001
        self.pushed.append(branch)


class FakePR:
    last = None

    def __init__(self, provider, repo, **kw):  # noqa: ANN001
        self.provider = provider
        self.repo = repo
        self.evidence_posts: list[int] = []
        FakePR.last = self

    def create_pr(self, *, title, base, head, body, draft):  # noqa: ANN001
        return PrInfo(
            provider="github",
            repo=self.repo,
            number=11,
            url="https://github.com/o/r/pull/11",
            title=title,
            source_branch=head,
            target_branch=base,
            state="draft" if draft else "open",
        )

    def post_evidence(self, pr_number, *, branch, evidence, steps_completed=None):  # noqa: ANN001
        self.evidence_posts.append(pr_number)

    def read_feedback(self, pr_number):  # noqa: ANN001
        return []


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(flow_mod, "WorktreeManager", FakeWorktree)
    monkeypatch.setattr(flow_mod, "SimplicioExecutor", FakeExecutor)
    monkeypatch.setattr(flow_mod, "EvidenceCollector", FakeEvidence)
    monkeypatch.setattr(flow_mod, "GitOps", FakeGit)
    monkeypatch.setattr(flow_mod, "PullRequestManager", FakePR)
    monkeypatch.setattr(flow_mod, "detect_tech", lambda p: type("T", (), {"primary_tech": "python"})())


def _flow(operator, tmp_path):
    target = RepoTarget(
        path=tmp_path,
        name="o/r",
        repo_slug="o/r",
        tech="python",
        test_command="pytest",
        base_branch="develop",
        pr_provider="github",
    )
    return SprintFlow(operator, target, draft_prs=True)


def test_deliver_item_happy_path(patched, tmp_path):
    item = SprintItem(id="1", key="ABC-1", type="Task", title="do x", status="open")
    op = FakeOperator([item])
    outcome = _flow(op, tmp_path).deliver_item(item)
    names = [s.name for s in outcome.steps]
    assert any(n.startswith("execute:") for n in names)
    assert any(n.startswith("evidence:") for n in names)
    assert any(n.startswith("commit:") for n in names)
    assert any(n.startswith("pr:") for n in names)
    assert outcome.pr is not None and outcome.pr.number == 11
    assert op.status_calls and op.status_calls[0][1] == "In Review"
    assert FakePR.last.evidence_posts == [11]


def test_run_aggregates_report(patched, tmp_path):
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open"),
    ]
    report = _flow(FakeOperator(items), tmp_path).run()
    assert len(report.prs) == 2
    assert report.failed is False
    assert "2 item" in report.summary


def test_deliver_item_skips_when_executor_fails(patched, tmp_path, monkeypatch):
    class FailingExec(FakeExecutor):
        def run_item(self, item, *, stack=None, target=None, repo=None):  # noqa: ANN001
            return StepReport(step=3, name=f"execute:{item.key}", status="failed", message="boom")

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", FailingExec)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="x", status="open")
    outcome = _flow(FakeOperator([item]), tmp_path).deliver_item(item)
    assert outcome.pr is None
    assert outcome.steps[-1].status == "failed"


def test_revise_pr_runs_simplicio_on_feedback(patched, tmp_path, monkeypatch):
    class FeedbackPR(FakePR):
        def read_feedback(self, pr_number):  # noqa: ANN001
            from sendsprint.github_integration import ReviewFeedback

            return [ReviewFeedback(reviewer="bob", body="rename it", state="CHANGES_REQUESTED")]

    monkeypatch.setattr(flow_mod, "PullRequestManager", FeedbackPR)
    # worktree_dir must "exist" — point at tmp_path which exists
    item = SprintItem(id="1", key="ABC-1", type="Task", title="x", status="open")
    steps = _flow(FakeOperator([item]), tmp_path).revise_pr(11, branch="feature/x", item_key="ABC-1")
    assert any(s.name == "revise:pr-feedback" for s in steps)
