"""Integration test for the SprintFlow orchestrator with faked components."""

from __future__ import annotations

import json
import signal

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

    def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
        return StepReport(step=3, name=f"execute:{item.key}", status="ok", message="ok")

    def index(self, repo_path=None, *, repo=None):  # noqa: ANN001
        return StepReport(step=2, name="mapper:index", repo=repo, status="skipped")

    def revise(self, feedback, *, stack=None, target=None, repo=None):  # noqa: ANN001
        return StepReport(step=3, name="revise:pr-feedback", status="ok")


class FakeEvidence:
    def __init__(self, work_dir, *, item_key, **kw):  # noqa: ANN001
        self.work_dir = work_dir
        self.item_key = item_key

    def collect_tests(self, cmd):  # noqa: ANN001
        return TestEvidence(kind="unit", title=cmd or "tests", passed=True, message="exit 0")

    def collect_detected(self, fingerprint):  # noqa: ANN001
        return [TestEvidence(kind="unit", title=fingerprint.primary_tech, passed=True)]

    def capture_screenshot(self, url, *, name="screen", screenshot_fn=None):  # noqa: ANN001
        return None

    def render_delivery_video(self, *, enabled=True, name="delivery", env=None, timeout_s=300):
        return None

    def write_manifest(self, evidence, *, steps_completed=None, review_feedback=None):  # noqa: ANN001
        path = self.work_dir / ".sendsprint/evidence" / self.item_key / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
        return path


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

    def post_evidence(  # noqa: ANN001
        self, pr_number, *, branch, evidence, steps_completed=None, review_feedback=None
    ):
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
    monkeypatch.setattr(
        flow_mod, "detect_tech", lambda p: type("T", (), {"primary_tech": "python"})()
    )


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


def test_deliver_item_records_mapper_and_fanout_steps(patched, tmp_path):
    import json
    import subprocess

    from sendsprint.prompt import PromptFanout

    kernel = tmp_path / "subagent_runtime.py"
    kernel.write_text("# stub")
    report = json.dumps(
        {
            "requested": 3,
            "completed": 3,
            "failed": 0,
            "elapsed_s": 0.1,
            "provider": "deepseek",
            "model": "m",
            "usage": {"cost_usd": 0.0},
            "results": [{"agent_id": 0, "ok": True, "text": "idea"}],
        }
    )

    def run(argv, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(argv, 0, report, "")

    item = SprintItem(id="1", key="ABC-1", type="Task", title="do x", status="open")
    flow = _flow(FakeOperator([item]), tmp_path)
    flow.fanout = PromptFanout(kernel_path=kernel, runner=run, subagents=3)
    outcome = flow.deliver_item(item)
    names = [s.name for s in outcome.steps]
    assert any(n.startswith("mapper:") for n in names)
    assert any(n.startswith("fanout:") for n in names)
    # The mapper spec file lands in the worktree under .specs/.
    assert list(tmp_path.glob(".specs/sprints/*/*.task.md"))


def test_deliver_item_uses_detected_evidence_without_explicit_test_command(
    patched, tmp_path, monkeypatch
):
    class RecordingEvidence(FakeEvidence):
        fingerprints = []

        def collect_detected(self, fingerprint):  # noqa: ANN001
            self.__class__.fingerprints.append(fingerprint)
            return [TestEvidence(kind="unit", title="vitest", passed=True, message="exit 0")]

    fingerprint = type("T", (), {"primary_tech": "node", "techs": ["node", "vitest"]})()
    monkeypatch.setattr(flow_mod, "EvidenceCollector", RecordingEvidence)
    monkeypatch.setattr(flow_mod, "detect_tech", lambda p: fingerprint)
    target = RepoTarget(
        path=tmp_path,
        name="o/r",
        repo_slug="o/r",
        tech=None,
        test_command=None,
        base_branch="develop",
        pr_provider="github",
    )

    item = SprintItem(id="1", key="ABC-1", type="Task", title="do x", status="open")
    outcome = SprintFlow(FakeOperator([item]), target, draft_prs=True).deliver_item(item)

    assert outcome.pr is not None
    assert RecordingEvidence.fingerprints == [fingerprint]


def test_collect_evidence_renders_video_when_enabled(patched, tmp_path, monkeypatch):
    class RecordingEvidence(FakeEvidence):
        videos: int = 0

        def capture_screenshot(self, url, *, name="screen", screenshot_fn=None):  # noqa: ANN001
            return TestEvidence(kind="screenshot", title=url, passed=True, path="screen.png")

        def render_delivery_video(self, *, enabled=True, name="delivery", env=None, timeout_s=300):
            self.__class__.videos += 1
            return TestEvidence(
                kind="video", title="delivery video", passed=True, path="delivery.mp4"
            )

    monkeypatch.setattr(flow_mod, "EvidenceCollector", RecordingEvidence)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="do x", status="open")
    target = RepoTarget(
        path=tmp_path,
        name="o/r",
        repo_slug="o/r",
        tech="html",
        test_command="pytest",
        frontend_url="http://localhost:3000",
        evidence_video=True,
    )

    outcome = SprintFlow(FakeOperator([item]), target, draft_prs=True).deliver_item(item)

    assert outcome.pr is not None
    assert RecordingEvidence.videos == 1
    evidence = next(step.evidence for step in outcome.steps if step.name.startswith("evidence:"))
    assert any(ev.kind == "video" and ev.path == "delivery.mp4" for ev in evidence)


def test_collect_evidence_skips_missing_video_without_failing_step(patched, tmp_path, monkeypatch):
    class RecordingEvidence(FakeEvidence):
        def capture_screenshot(self, url, *, name="screen", screenshot_fn=None):  # noqa: ANN001
            return TestEvidence(kind="screenshot", title=url, passed=True, path="screen.png")

        def render_delivery_video(self, *, enabled=True, name="delivery", env=None, timeout_s=300):
            return TestEvidence(
                kind="video",
                title="delivery video",
                passed=False,
                status="skipped",
                message="hyperframes not available; skipped",
            )

    monkeypatch.setattr(flow_mod, "EvidenceCollector", RecordingEvidence)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="do x", status="open")
    target = RepoTarget(
        path=tmp_path,
        name="o/r",
        repo_slug="o/r",
        tech="html",
        test_command="pytest",
        frontend_url="http://localhost:3000",
        evidence_video=True,
    )

    outcome = SprintFlow(FakeOperator([item]), target, draft_prs=True).deliver_item(item)

    evidence_step = next(step for step in outcome.steps if step.name.startswith("evidence:"))
    assert evidence_step.status == "ok"
    assert outcome.pr is not None
    assert any(ev.kind == "video" and ev.status == "skipped" for ev in evidence_step.evidence)


def test_run_aggregates_report(patched, tmp_path):
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open"),
    ]
    report = _flow(FakeOperator(items), tmp_path).run()
    assert len(report.prs) == 2
    assert report.failed is False
    assert "2 item" in report.summary


def test_run_emits_progress_events_with_elapsed_and_summary(patched, tmp_path):
    events: list[flow_mod.ProgressEvent] = []
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open"),
    ]

    report = _flow(FakeOperator(items), tmp_path).run(progress=events.append)

    assert report.failed is False
    assert [event.kind for event in events] == [
        "run_started",
        "item_started",
        "item_finished",
        "item_started",
        "item_finished",
        "run_finished",
    ]
    assert events[0].total_items == 2
    assert [item.key for item in events[0].items] == ["ABC-1", "ABC-2"]
    finished = [event for event in events if event.kind == "item_finished"]
    assert all(event.status == "ok" for event in finished)
    assert all(event.dod is True for event in finished)
    assert all(event.elapsed_s is not None for event in finished)
    assert events[-1].ok_count == 2
    assert events[-1].cost_usd is None


def test_run_writes_state_before_first_item(patched, tmp_path, monkeypatch):
    state_path = tmp_path / ".sendsprint" / "state" / "sprint-s1.json"

    class StateAwareExec(FakeExecutor):
        def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
            assert state_path.exists()
            data = json.loads(state_path.read_text(encoding="utf-8"))
            assert data["pending"] == ["ABC-1"]
            return super().run_item(
                item, stack=stack, target=target, repo=repo, extra_context=extra_context
            )

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", StateAwareExec)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open")

    report = _flow(FakeOperator([item]), tmp_path).run()

    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["completed"] == ["ABC-1"]
    assert data["failed"] == []
    assert data["pending"] == []
    assert data["last_pr"] == {"ABC-1": 11}
    assert report.failed is False


def test_run_resume_delivers_only_pending_items(patched, tmp_path, monkeypatch):
    state_path = tmp_path / ".sendsprint" / "state" / "sprint-s1.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "sprint_slug": "sprint-s1",
                "completed": ["ABC-1"],
                "failed": [],
                "pending": ["ABC-2"],
                "last_pr": {"ABC-1": 7},
            }
        ),
        encoding="utf-8",
    )

    class RecordingExec(FakeExecutor):
        calls: list[str] = []

        def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
            self.__class__.calls.append(item.key)
            return super().run_item(
                item, stack=stack, target=target, repo=repo, extra_context=extra_context
            )

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", RecordingExec)
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open"),
    ]

    report = _flow(FakeOperator(items), tmp_path).run(resume=True)

    assert RecordingExec.calls == ["ABC-2"]
    assert len(report.prs) == 1
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["completed"] == ["ABC-1", "ABC-2"]
    assert data["pending"] == []
    assert any("skipped 1 settled" in note for note in report.notes)


def test_run_resume_without_state_fails_before_delivery(patched, tmp_path, monkeypatch):
    class UnexpectedExecutor(FakeExecutor):
        def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
            raise AssertionError("resume without state must not deliver items")

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", UnexpectedExecutor)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open")

    report = _flow(FakeOperator([item]), tmp_path).run(resume=True)

    assert report.failed is True
    assert report.prs == []
    assert report.steps[-1].name == "state:load"
    assert "not found" in (report.steps[-1].message or "")


def test_run_stop_file_drains_after_current_item(patched, tmp_path, monkeypatch):
    stop_path = tmp_path / ".sendsprint" / "state" / "STOP"

    class StopAfterFirstExec(FakeExecutor):
        calls: list[str] = []

        def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
            self.__class__.calls.append(item.key)
            if item.key == "ABC-1":
                stop_path.parent.mkdir(parents=True, exist_ok=True)
                stop_path.write_text("stop", encoding="utf-8")
            return super().run_item(
                item, stack=stack, target=target, repo=repo, extra_context=extra_context
            )

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", StopAfterFirstExec)
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open"),
    ]

    report = _flow(FakeOperator(items), tmp_path).run()
    data = json.loads((tmp_path / ".sendsprint" / "state" / "sprint-s1.json").read_text())

    assert StopAfterFirstExec.calls == ["ABC-1"]
    assert report.cancelled is True
    assert report.failed is False
    assert data["completed"] == ["ABC-1"]
    assert data["pending"] == ["ABC-2"]
    assert "cancelled" in (report.summary or "")


def test_run_sigint_drains_after_current_item(patched, tmp_path, monkeypatch):
    class InterruptingExec(FakeExecutor):
        calls: list[str] = []

        def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
            self.__class__.calls.append(item.key)
            if item.key == "ABC-1":
                signal.raise_signal(signal.SIGINT)
            return super().run_item(
                item, stack=stack, target=target, repo=repo, extra_context=extra_context
            )

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", InterruptingExec)
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open"),
    ]

    report = _flow(FakeOperator(items), tmp_path).run()

    assert InterruptingExec.calls == ["ABC-1"]
    assert report.cancelled is True
    assert report.failed is False
    assert any("sigint" in note for note in report.notes)
    assert (tmp_path / ".specs" / "sprints" / "sprint-s1" / "RETROSPECTIVE.md").exists()


def test_run_writes_retrospective_by_default(patched, tmp_path):
    item = SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open")
    report = _flow(FakeOperator([item]), tmp_path).run()
    retro = tmp_path / ".specs" / "sprints" / "sprint-s1" / "RETROSPECTIVE.md"
    assert retro.exists()
    assert any(step.name == "retro:write" and step.status == "ok" for step in report.steps)
    assert "https://github.com/o/r/pull/11" in retro.read_text(encoding="utf-8")


def test_run_can_skip_retrospective(patched, tmp_path):
    item = SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open")
    report = _flow(FakeOperator([item]), tmp_path).run(retro=False)

    assert not any(step.name == "retro:write" for step in report.steps)
    assert not list(tmp_path.glob(".specs/sprints/*/RETROSPECTIVE.md"))


def test_run_marks_retrospective_write_failure(patched, tmp_path, monkeypatch):
    def fail_retro(self, sprint, report):  # noqa: ANN001
        raise OSError("cannot write retro")

    monkeypatch.setattr(flow_mod.MapperAdapter, "write_retrospective", fail_retro)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open")

    report = _flow(FakeOperator([item]), tmp_path).run()

    retro_step = next(step for step in report.steps if step.name == "retro:write")
    assert retro_step.status == "failed"
    assert report.failed is True


def test_run_aborts_on_preflight_errors(patched, tmp_path, monkeypatch):
    class UnexpectedExecutor(FakeExecutor):
        def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
            raise AssertionError("executor should not run after failed pre-flight")

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", UnexpectedExecutor)
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open", parent_key="ABC-2"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open", parent_key="ABC-1"),
    ]
    report = _flow(FakeOperator(items), tmp_path).run()
    assert report.failed is True
    assert report.steps == [
        StepReport(
            step=1,
            name="validate:sprint",
            status="failed",
            message=report.steps[0].message,
        )
    ]
    assert "parent_cycle" in (report.steps[0].message or "")
    assert report.prs == []


def test_run_validate_only_exits_before_delivery(patched, tmp_path, monkeypatch):
    class UnexpectedWorktree(FakeWorktree):
        def create(self, branch, base="HEAD"):  # noqa: ANN001
            raise AssertionError("worktree should not be created in validate-only mode")

    monkeypatch.setattr(flow_mod, "WorktreeManager", UnexpectedWorktree)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="x", status="open")
    report = _flow(FakeOperator([item]), tmp_path).run(validate_only=True)
    assert report.failed is False
    assert [step.name for step in report.steps] == ["validate:sprint"]
    assert report.steps[0].status == "ok"
    assert report.prs == []


def test_topological_order_places_parent_before_children():
    items = [
        SprintItem(
            id="3", key="ABC-3", type="Task", title="task", status="open", parent_key="ABC-2"
        ),
        SprintItem(
            id="2", key="ABC-2", type="Story", title="story", status="open", parent_key="ABC-1"
        ),
        SprintItem(id="1", key="ABC-1", type="Epic", title="epic", status="open"),
        SprintItem(id="4", key="ABC-4", type="Task", title="standalone", status="open"),
    ]
    ordered = flow_mod._topological_order(items)
    assert [item.key for item in ordered] == ["ABC-1", "ABC-4", "ABC-2", "ABC-3"]


def test_topological_order_preserves_items_without_keys():
    items = [
        SprintItem(id="0", key="", type="Task", title="imported", status="open"),
        SprintItem(
            id="2", key="ABC-2", type="Task", title="child", status="open", parent_key="ABC-1"
        ),
        SprintItem(id="1", key="ABC-1", type="Story", title="parent", status="open"),
    ]
    ordered = flow_mod._topological_order(items)
    assert [item.id for item in ordered] == ["0", "1", "2"]


def test_run_bootstraps_missing_mapper_index(patched, tmp_path, monkeypatch):
    class BootstrappingExec(FakeExecutor):
        def index(self, repo_path=None, *, repo=None):  # noqa: ANN001
            project_map = tmp_path / ".simplicio" / "project-map.json"
            project_map.parent.mkdir(parents=True)
            project_map.write_text("{}")
            return StepReport(step=2, name="mapper:index", repo=repo, status="ok")

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", BootstrappingExec)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="x", status="open")
    report = _flow(FakeOperator([item]), tmp_path).run()
    assert (tmp_path / ".simplicio" / "project-map.json").exists()
    assert any(step.name == "mapper:index" and step.status == "ok" for step in report.steps)


def test_run_skips_mapper_bootstrap_when_index_exists(patched, tmp_path, monkeypatch):
    project_map = tmp_path / ".simplicio" / "project-map.json"
    project_map.parent.mkdir(parents=True)
    project_map.write_text("{}")

    class UnexpectedIndexExec(FakeExecutor):
        def index(self, repo_path=None, *, repo=None):  # noqa: ANN001
            raise AssertionError("mapper index should not run when project-map exists")

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", UnexpectedIndexExec)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="x", status="open")
    report = _flow(FakeOperator([item]), tmp_path).run()
    assert any(
        step.name == "mapper:index" and "already present" in (step.message or "")
        for step in report.steps
    )


def test_run_records_mapper_bootstrap_gap_as_note(patched, tmp_path, monkeypatch):
    class MissingIndexExec(FakeExecutor):
        def index(self, repo_path=None, *, repo=None):  # noqa: ANN001
            return StepReport(
                step=2,
                name="mapper:index",
                repo=repo,
                status="skipped",
                message="simplicio not installed; mapper context degraded",
            )

    monkeypatch.setattr(flow_mod, "SimplicioExecutor", MissingIndexExec)
    item = SprintItem(id="1", key="ABC-1", type="Task", title="x", status="open")
    report = _flow(FakeOperator([item]), tmp_path).run()
    assert "mapper context degraded" in report.notes[0]


def test_deliver_item_skips_when_executor_fails(patched, tmp_path, monkeypatch):
    class FailingExec(FakeExecutor):
        def run_item(self, item, *, stack=None, target=None, repo=None, extra_context=None):  # noqa: ANN001
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
    steps = _flow(FakeOperator([item]), tmp_path).revise_pr(
        11, branch="feature/x", item_key="ABC-1"
    )
    assert any(s.name == "revise:pr-feedback" for s in steps)
