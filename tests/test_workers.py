"""Tests for sendsprint.workers — Python worker, Go spec, and resolver."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from sendsprint.contracts import (
    CommandType,
    EventType,
    RunCommand,
    RunEvent,
    WorkerCapability,
    WorkerStack,
)
from sendsprint.workers.go_spec import (
    GO_WORKER_BINARY,
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    GoWorkerProxy,
    GoWorkerSpec,
    detect_go_worker,
)
from sendsprint.workers.python_worker import (
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_MEM_LIMIT_MB,
    DEFAULT_QUEUE_SIZE,
    PythonWorker,
)
from sendsprint.workers.resolver import resolve_worker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cmd(
    run_id: str = "run-1", cmd_type: CommandType = CommandType.plan, timeout_s: int = 300
) -> RunCommand:
    return RunCommand(command_type=cmd_type, run_id=run_id, timeout_s=timeout_s)


# ── PythonWorker ──────────────────────────────────────────────────────────


class TestPythonWorkerLifecycle:
    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        w = PythonWorker(worker_id="test-w")
        assert not w._started
        await w.start()
        assert w._started
        await w.stop()
        assert not w._started

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        await w.start()  # no error
        assert w._started
        await w.stop()

    @pytest.mark.asyncio
    async def test_queue_before_start_raises(self) -> None:
        w = PythonWorker(worker_id="test-w")
        with pytest.raises(RuntimeError, match="not started"):
            await w.queue(_cmd())


class TestPythonWorkerQueue:
    @pytest.mark.asyncio
    async def test_queue_and_complete(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        run_id = await w.queue(_cmd("run-abc"))
        assert run_id == "run-abc"
        # Let the task finish
        await asyncio.sleep(0.05)
        snap = w.status("run-abc")
        assert snap["state"] == "completed"
        await w.stop()


class TestPythonWorkerCancel:
    @pytest.mark.asyncio
    async def test_cancel_running_task(self) -> None:
        async def slow_exec(cmd: RunCommand) -> RunEvent:
            await asyncio.sleep(10)
            return RunEvent(event_type=EventType.completed, run_id=cmd.run_id)

        w = PythonWorker(worker_id="test-w", executor=slow_exec)
        await w.start()
        await w.queue(_cmd("run-slow"))
        await asyncio.sleep(0.05)
        event = await w.cancel("run-slow")
        assert event.event_type == EventType.cancelled
        assert event.run_id == "run-slow"
        await w.stop()

    @pytest.mark.asyncio
    async def test_cancel_unknown_raises(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        with pytest.raises(KeyError, match="unknown run_id"):
            await w.cancel("nonexistent")
        await w.stop()

    @pytest.mark.asyncio
    async def test_cancel_already_terminal(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        await w.queue(_cmd("run-done"))
        await asyncio.sleep(0.05)
        event = await w.cancel("run-done")
        assert event.error == "already terminal"
        await w.stop()


class TestPythonWorkerHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_returns_event(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        hb = w.heartbeat()
        assert hb.event_type == EventType.heartbeat
        assert hb.run_id == "__heartbeat__"
        assert hb.data["worker_id"] == "test-w"
        assert "active" in hb.data
        assert "queued" in hb.data
        await w.stop()


class TestPythonWorkerStatus:
    @pytest.mark.asyncio
    async def test_status_all(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        snap = w.status()
        assert snap["worker_id"] == "test-w"
        assert snap["started"] is True
        assert snap["tasks"] == {}
        await w.stop()

    @pytest.mark.asyncio
    async def test_status_unknown_raises(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        with pytest.raises(KeyError, match="unknown run_id"):
            w.status("ghost")
        await w.stop()

    @pytest.mark.asyncio
    async def test_status_single_task(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        await w.queue(_cmd("run-1"))
        await asyncio.sleep(0.05)
        snap = w.status("run-1")
        assert snap["run_id"] == "run-1"
        assert snap["state"] in ("completed", "running")
        await w.stop()


class TestPythonWorkerLogTail:
    @pytest.mark.asyncio
    async def test_log_tail_default(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        lines = w.log_tail()
        assert len(lines) >= 1  # at least the "started" line
        assert "started" in lines[0]
        await w.stop()

    @pytest.mark.asyncio
    async def test_log_tail_limit(self) -> None:
        w = PythonWorker(worker_id="test-w")
        await w.start()
        await w.queue(_cmd("r1"))
        await w.queue(_cmd("r2"))
        await asyncio.sleep(0.05)
        lines = w.log_tail(2)
        assert len(lines) == 2
        await w.stop()


class TestPythonWorkerCapability:
    def test_capability_descriptor(self) -> None:
        w = PythonWorker(worker_id="test-w", max_concurrency=8)
        cap = w.capability()
        assert isinstance(cap, WorkerCapability)
        assert cap.worker_id == "test-w"
        assert cap.stack == WorkerStack.python
        assert cap.max_concurrency == 8
        assert CommandType.plan in cap.supported_commands
        assert cap.metadata["queue_size"] == DEFAULT_QUEUE_SIZE


class TestPythonWorkerTimeout:
    @pytest.mark.asyncio
    async def test_task_timeout(self) -> None:
        async def hang(cmd: RunCommand) -> RunEvent:
            await asyncio.sleep(999)
            return RunEvent(event_type=EventType.completed, run_id=cmd.run_id)

        w = PythonWorker(worker_id="test-w", executor=hang)
        await w.start()
        cmd = _cmd("run-timeout", timeout_s=1)
        await w.queue(cmd)
        # Wait for timeout
        await asyncio.sleep(1.5)
        snap = w.status("run-timeout")
        assert snap["state"] == "failed"
        assert "timeout" in (snap["error"] or "")
        await w.stop()


class TestPythonWorkerExecutorError:
    @pytest.mark.asyncio
    async def test_executor_exception(self) -> None:
        async def bad_exec(cmd: RunCommand) -> RunEvent:
            raise ValueError("boom")

        w = PythonWorker(worker_id="test-w", executor=bad_exec)
        await w.start()
        await w.queue(_cmd("run-err"))
        await asyncio.sleep(0.05)
        snap = w.status("run-err")
        assert snap["state"] == "failed"
        assert snap["error"] == "boom"
        await w.stop()


class TestPythonWorkerDefaults:
    def test_default_values(self) -> None:
        w = PythonWorker()
        assert w.max_concurrency == DEFAULT_MAX_CONCURRENCY
        assert w.queue_size == DEFAULT_QUEUE_SIZE
        assert w.mem_limit_mb == DEFAULT_MEM_LIMIT_MB
        assert w.worker_id.startswith("py-")


# ── GoWorkerSpec ──────────────────────────────────────────────────────────


class TestGoWorkerSpec:
    def test_spec_defaults(self) -> None:
        spec = GoWorkerSpec()
        assert spec.binary_name == GO_WORKER_BINARY
        assert spec.transport == "stdio"
        assert "queue" in spec.supported_actions
        assert "shutdown" in spec.supported_actions
        assert len(spec.supported_actions) == 7

    def test_request_schema_structure(self) -> None:
        assert REQUEST_SCHEMA["type"] == "object"
        assert "action" in REQUEST_SCHEMA["properties"]
        assert "version" in REQUEST_SCHEMA["properties"]
        assert set(REQUEST_SCHEMA["required"]) == {"action", "version"}

    def test_response_schema_structure(self) -> None:
        assert RESPONSE_SCHEMA["type"] == "object"
        assert "ok" in RESPONSE_SCHEMA["properties"]
        assert RESPONSE_SCHEMA["required"] == ["ok"]

    def test_spec_is_frozen(self) -> None:
        spec = GoWorkerSpec()
        with pytest.raises(ValueError):
            spec.binary_name = "other"  # type: ignore[misc]

    def test_spec_json_roundtrip(self) -> None:
        spec = GoWorkerSpec()
        data = json.loads(spec.model_dump_json())
        restored = GoWorkerSpec.model_validate(data)
        assert restored.binary_name == spec.binary_name
        assert restored.transport == spec.transport


class TestDetectGoWorker:
    def test_not_found(self) -> None:
        with patch("sendsprint.workers.go_spec.shutil.which", return_value=None):
            assert detect_go_worker() is False

    def test_found(self) -> None:
        with patch(
            "sendsprint.workers.go_spec.shutil.which",
            return_value="/usr/local/bin/sendsprint-worker",
        ):
            assert detect_go_worker() is True


class TestGoWorkerProxy:
    def test_capability(self) -> None:
        proxy = GoWorkerProxy()
        cap = proxy.capability()
        assert cap.stack == WorkerStack.go
        assert cap.max_concurrency == 16
        assert CommandType.plan in cap.supported_commands

    def test_available_false(self) -> None:
        proxy = GoWorkerProxy()
        with patch("sendsprint.workers.go_spec.shutil.which", return_value=None):
            assert proxy.available() is False

    def test_send_binary_missing(self) -> None:
        proxy = GoWorkerProxy()
        with (
            patch("sendsprint.workers.go_spec.shutil.which", return_value=None),
            pytest.raises(RuntimeError, match="not found on PATH"),
        ):
            proxy.send("heartbeat")

    def test_send_ok_response(self) -> None:
        proxy = GoWorkerProxy()
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"ok": True, "data": {"status": "alive"}}),
                "stderr": "",
            },
        )()
        with (
            patch("sendsprint.workers.go_spec.shutil.which", return_value="/bin/sw"),
            patch("sendsprint.workers.go_spec.subprocess.run", return_value=mock_result),
        ):
            resp = proxy.send("heartbeat")
            assert resp["ok"] is True
            assert resp["data"]["status"] == "alive"

    def test_send_error_response(self) -> None:
        proxy = GoWorkerProxy()
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"ok": False, "error": "queue full"}),
                "stderr": "",
            },
        )()
        with (
            patch("sendsprint.workers.go_spec.shutil.which", return_value="/bin/sw"),
            patch("sendsprint.workers.go_spec.subprocess.run", return_value=mock_result),
            pytest.raises(RuntimeError, match="queue full"),
        ):
            proxy.send("queue", run_id="r1")

    def test_send_nonzero_exit(self) -> None:
        proxy = GoWorkerProxy()
        mock_result = type(
            "R",
            (),
            {
                "returncode": 1,
                "stdout": "",
                "stderr": "segfault",
            },
        )()
        with (
            patch("sendsprint.workers.go_spec.shutil.which", return_value="/bin/sw"),
            patch("sendsprint.workers.go_spec.subprocess.run", return_value=mock_result),
            pytest.raises(RuntimeError, match="exited 1"),
        ):
            proxy.send("status")

    def test_send_invalid_json(self) -> None:
        proxy = GoWorkerProxy()
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": "not json",
                "stderr": "",
            },
        )()
        with (
            patch("sendsprint.workers.go_spec.shutil.which", return_value="/bin/sw"),
            patch("sendsprint.workers.go_spec.subprocess.run", return_value=mock_result),
            pytest.raises(RuntimeError, match="invalid JSON"),
        ):
            proxy.send("status")

    def test_queue_via_proxy(self) -> None:
        proxy = GoWorkerProxy()
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"ok": True}),
                "stderr": "",
            },
        )()
        with (
            patch("sendsprint.workers.go_spec.shutil.which", return_value="/bin/sw"),
            patch("sendsprint.workers.go_spec.subprocess.run", return_value=mock_result),
        ):
            rid = proxy.queue(_cmd("run-go"))
            assert rid == "run-go"

    def test_cancel_via_proxy(self) -> None:
        proxy = GoWorkerProxy()
        mock_result = type(
            "R",
            (),
            {
                "returncode": 0,
                "stdout": json.dumps({"ok": True, "event": {"note": "done"}}),
                "stderr": "",
            },
        )()
        with (
            patch("sendsprint.workers.go_spec.shutil.which", return_value="/bin/sw"),
            patch("sendsprint.workers.go_spec.subprocess.run", return_value=mock_result),
        ):
            event = proxy.cancel("run-go")
            assert event.event_type == EventType.cancelled
            assert event.source_stack == WorkerStack.go


# ── Resolver ──────────────────────────────────────────────────────────────


class TestResolver:
    def test_fallback_to_python(self) -> None:
        with patch("sendsprint.workers.resolver.detect_go_worker", return_value=False):
            w = resolve_worker()
            assert isinstance(w, PythonWorker)

    def test_prefer_go_when_available(self) -> None:
        with patch("sendsprint.workers.resolver.detect_go_worker", return_value=True):
            w = resolve_worker()
            assert isinstance(w, GoWorkerProxy)

    def test_prefer_go_false(self) -> None:
        with patch("sendsprint.workers.resolver.detect_go_worker", return_value=True):
            w = resolve_worker(prefer_go=False)
            assert isinstance(w, PythonWorker)

    def test_custom_concurrency(self) -> None:
        with patch("sendsprint.workers.resolver.detect_go_worker", return_value=False):
            w = resolve_worker(max_concurrency=8)
            assert isinstance(w, PythonWorker)
            assert w.max_concurrency == 8


# ── Package __init__ ──────────────────────────────────────────────────────


class TestPackageImports:
    def test_public_api(self) -> None:
        from sendsprint.workers import (
            GoWorkerProxy,
            GoWorkerSpec,
            PythonWorker,
            detect_go_worker,
            resolve_worker,
        )

        assert PythonWorker is not None
        assert GoWorkerProxy is not None
        assert GoWorkerSpec is not None
        assert callable(detect_go_worker)
        assert callable(resolve_worker)
