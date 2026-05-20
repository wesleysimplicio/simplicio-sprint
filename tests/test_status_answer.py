from sendsprint.api.runs.status_answer import render_status_answer
from sendsprint.api.schemas import AgentRunSnapshot, AgentTimelineEvent


def _snapshot(**updates):
    base = {
        "run_id": "run-1",
        "sprint_id": "sprint-1",
        "provider": "jira",
        "state": "running",
        "mode": "selected",
        "item_keys": ["APP-1"],
    }
    base.update(updates)
    return AgentRunSnapshot(**base)


def test_status_answer_renders_current_step_and_next_action() -> None:
    snapshot = _snapshot(
        current_step=2,
        current_step_name="architecture",
        current_step_status="running",
        progress=0.2,
        evidence_paths=["evidence/run-1/map.json"],
        timeline=[AgentTimelineEvent(type="step", name="agent.codex.plan")],
    )

    answer = render_status_answer(snapshot, adapter="codex")

    assert answer.adapter == "codex"
    assert answer.current_step == "step 2: architecture (running)"
    assert answer.last_evidence == "evidence/run-1/map.json"
    assert answer.active_agents == ["agent.codex.plan", "sendsprint"]
    assert answer.next_action == "continue architecture"


def test_status_answer_reports_unknown_without_guessing() -> None:
    answer = render_status_answer(_snapshot(state="queued"), adapter="unknown")

    assert answer.adapter == "generic"
    assert answer.current_step == "unknown"
    assert answer.next_action == "wait for worker to start"


def test_status_answer_prioritizes_failure_blocker() -> None:
    answer = render_status_answer(
        _snapshot(state="failed", failed=True, blockers=["pytest failed"]),
        adapter="hermes",
    )

    assert answer.adapter == "hermes"
    assert "pytest failed" in answer.summary
    assert answer.next_action == "inspect blockers and queue rework or cancel command"
