"""Tests for the unattended watch trigger."""

from __future__ import annotations

from sendsprint.flow import RepoTarget, SprintFlow
from sendsprint.models.reports import StepReport
from sendsprint.models.sprint import Sprint, SprintItem
from sendsprint.scope import build_scope
from sendsprint.watch import Watcher


class StubOperator:
    source = "github"

    def __init__(self, items):
        self._items = items

    def read_sprint(self, **kwargs):  # noqa: ANN003
        return Sprint(id="s", name="s", source="github", items=self._items)


def _flow(items, tmp_path):
    op = StubOperator(items)
    target = RepoTarget(path=tmp_path, name="o/r", repo_slug="o/r")
    flow = SprintFlow(op, target, scope=build_scope(mode="all"))
    return flow


def test_run_once_delivers_pending_and_records(tmp_path, monkeypatch):
    items = [
        SprintItem(id="1", key="ABC-1", type="Task", title="a", status="open"),
        SprintItem(id="2", key="ABC-2", type="Task", title="b", status="open"),
    ]
    flow = _flow(items, tmp_path)
    delivered_keys: list[str] = []

    def fake_deliver(item):  # noqa: ANN001
        delivered_keys.append(item.key)
        from sendsprint.flow import ItemOutcome

        return ItemOutcome(
            item_key=item.key,
            steps=[StepReport(step=3, name=f"execute:{item.key}", status="ok")],
        )

    monkeypatch.setattr(flow, "deliver_item", fake_deliver)
    state = tmp_path / "state.json"
    watcher = Watcher(flow, state_path=state, max_per_cycle=1)

    r1 = watcher.run_once()
    assert delivered_keys == ["ABC-1"]
    assert state.exists()

    r2 = watcher.run_once()
    assert delivered_keys == ["ABC-1", "ABC-2"]  # second card on next cycle
    assert "delivered 1" in r1.summary and "delivered 1" in r2.summary

    r3 = watcher.run_once()
    assert delivered_keys == ["ABC-1", "ABC-2"]  # nothing left
    assert "delivered 0" in r3.summary
