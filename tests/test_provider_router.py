"""Tests for :class:`sendsprint.providers.router.ProviderRouter` and the registry."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

import pytest
import yaml

from sendsprint.models import SprintItem
from sendsprint.providers import (
    DispatchMode,
    DispatchTicket,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderError,
    ProviderRouter,
    PRResult,
    RunStatus,
    build_adapters,
    load_config,
)


def _make_item(key: str) -> SprintItem:
    return SprintItem(id=key, key=key, type="Task", title=key, status="To Do")


class _ScriptedAdapter(ProviderAdapter):
    """Adapter that flips queued -> done on the second poll, recording dispatches."""

    def __init__(
        self,
        name: str,
        dispatchable: bool = True,
        mode: DispatchMode = "cloud",
        fallback: str | None = None,
    ) -> None:
        self.name = name
        self._dispatchable = dispatchable
        self._mode = mode
        self._fallback = fallback
        self.dispatched: list[str] = []
        self._lock = Lock()
        self._statuses: dict[str, RunStatus] = {}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            mode=self._mode, dispatchable=self._dispatchable, fallback=self._fallback
        )

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        with self._lock:
            self.dispatched.append(item.key)
        ticket = DispatchTicket(
            run_id=f"{self.name}-{item.key}", provider=self.name, item_key=item.key
        )
        self._statuses[ticket.run_id] = "queued"
        return ticket

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        nxt: RunStatus = "done" if self._statuses[ticket.run_id] == "queued" else "done"
        self._statuses[ticket.run_id] = nxt
        return nxt

    def collect(self, ticket: DispatchTicket) -> PRResult:
        return PRResult(
            run_id=ticket.run_id,
            provider=self.name,
            item_key=ticket.item_key,
            status="done",
            pr_url=f"https://example.test/{self.name}/{ticket.item_key}",
            branch=f"{self.name}/{ticket.item_key}",
        )


class _StuckAdapter(_ScriptedAdapter):
    """Always reports ``running`` so the router has to time out."""

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        return "running"


class _FailingDispatchAdapter(_ScriptedAdapter):
    def dispatch(self, item: SprintItem) -> DispatchTicket:  # type: ignore[override]
        raise ProviderError(f"{self.name} refuses to dispatch")


def test_router_round_robins_across_dispatchable_adapters() -> None:
    claude = _ScriptedAdapter("claude")
    codex = _ScriptedAdapter("codex")
    cursor = _ScriptedAdapter("cursor", dispatchable=False, fallback="claude")

    router = ProviderRouter(
        [claude, codex, cursor], max_parallel=2, poll_interval_s=0, sleep=lambda _: None
    )
    items = [_make_item(f"T-{i}") for i in range(4)]

    results = router.dispatch_all(items)

    assert len(results) == 4
    assert all(r.status == "done" for r in results)
    # Cursor is dispatchable=false so the router never dispatches to it.
    assert cursor.dispatched == []
    # Round-robin across the two ready adapters in order.
    assert sorted(claude.dispatched) == ["T-0", "T-2"]
    assert sorted(codex.dispatched) == ["T-1", "T-3"]


def test_router_mixes_cloud_and_local_modes_in_round_robin() -> None:
    """Air-gapped projects can run with only local adapters; mixed setups also work."""
    claude_cloud = _ScriptedAdapter("claude", mode="cloud")
    ralph_local = _ScriptedAdapter("local-ralph", mode="local")
    goal_local = _ScriptedAdapter("local-goal", mode="local")

    router = ProviderRouter(
        [claude_cloud, ralph_local, goal_local],
        max_parallel=3,
        poll_interval_s=0,
        sleep=lambda _: None,
    )
    items = [_make_item(f"T-{i}") for i in range(6)]
    results = router.dispatch_all(items)

    assert all(r.status == "done" for r in results)
    # Each of the three dispatchable adapters got exactly two items.
    assert len(claude_cloud.dispatched) == 2
    assert len(ralph_local.dispatched) == 2
    assert len(goal_local.dispatched) == 2


def test_router_runs_with_local_adapters_only() -> None:
    """No cloud or GitHub access required when only local adapters are configured."""
    ralph_local = _ScriptedAdapter("local-ralph", mode="local")
    router = ProviderRouter([ralph_local], poll_interval_s=0, sleep=lambda _: None)
    results = router.dispatch_all([_make_item("T-1"), _make_item("T-2")])

    assert [r.status for r in results] == ["done", "done"]
    assert sorted(ralph_local.dispatched) == ["T-1", "T-2"]


def test_router_resolves_fallback_through_capabilities() -> None:
    claude = _ScriptedAdapter("claude")
    cursor = _ScriptedAdapter("cursor", dispatchable=False, fallback="claude")
    router = ProviderRouter([claude, cursor], poll_interval_s=0, sleep=lambda _: None)

    resolved = router.resolve_fallback(cursor)
    assert resolved is not None
    assert resolved.name == "claude"

    # Non-dispatchable adapter without a registered fallback yields None.
    standalone = _ScriptedAdapter("standalone", dispatchable=False, fallback="ghost")
    router2 = ProviderRouter([standalone, claude], poll_interval_s=0, sleep=lambda _: None)
    assert router2.resolve_fallback(standalone) is None


def test_router_rejects_when_no_dispatchable_adapter() -> None:
    cursor = _ScriptedAdapter("cursor", dispatchable=False, fallback="claude")
    router = ProviderRouter([cursor], poll_interval_s=0, sleep=lambda _: None)
    with pytest.raises(ProviderError):
        router.dispatch_all([_make_item("T-1")])


def test_router_records_dispatch_failure_as_failed_result() -> None:
    failing = _FailingDispatchAdapter("failing")
    router = ProviderRouter([failing], poll_interval_s=0, sleep=lambda _: None)
    results = router.dispatch_all([_make_item("T-1")])
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "refuses to dispatch" in (results[0].error or "")


def test_router_times_out_when_poll_never_terminates() -> None:
    stuck = _StuckAdapter("stuck")
    fake_now = iter([0.0, 0.0, 5.0, 5.0, 10.0, 10.0, 100.0, 100.0])
    router = ProviderRouter([stuck], poll_interval_s=0, timeout_s=1.0, sleep=lambda _: None)

    # Patch monotonic so the deadline trips deterministically without sleeping.
    import sendsprint.providers.router as router_module

    original = router_module.time.monotonic
    router_module.time.monotonic = lambda: next(fake_now)
    try:
        results = router.dispatch_all([_make_item("T-1")])
    finally:
        router_module.time.monotonic = original

    assert results[0].status == "failed"
    assert "exceeded" in (results[0].error or "")


def test_router_requires_at_least_one_adapter() -> None:
    with pytest.raises(ValueError):
        ProviderRouter([])


def test_registry_load_and_build(tmp_path: Path) -> None:
    config_path = tmp_path / "providers.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "max_parallel": 5,
                "poll_interval_s": 1,
                "timeout_s": 60,
                "providers": [
                    {"name": "claude"},
                    {"name": "cursor"},
                    {"name": "local-ralph"},
                    {"name": "local-goal"},
                ],
            }
        )
    )
    config = load_config(config_path)
    assert config.max_parallel == 5
    assert [p.name for p in config.providers] == [
        "claude",
        "cursor",
        "local-ralph",
        "local-goal",
    ]

    adapters = build_adapters(config)
    assert [a.name for a in adapters] == ["claude", "cursor", "local-ralph", "local-goal"]


def test_registry_rejects_unknown_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "providers.yml"
    config_path.write_text(yaml.safe_dump({"providers": [{"name": "nope"}]}))
    config = load_config(config_path)
    with pytest.raises(ValueError) as excinfo:
        build_adapters(config)
    assert "unknown provider 'nope'" in str(excinfo.value)
