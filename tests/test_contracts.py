"""Tests for sendsprint.contracts — serialization roundtrips and backwards compat."""

from __future__ import annotations

import json

import pytest

from sendsprint.contracts import (
    CONTRACT_VERSION,
    CommandType,
    ControlPlaneContract,
    EventType,
    RunCommand,
    RunEvent,
    WorkerCapability,
    WorkerStack,
    from_json,
    to_json,
)

# ── RunCommand ─────────────────────────────────────────────────────────────


class TestRunCommand:
    def test_minimal_construction(self) -> None:
        cmd = RunCommand(command_type=CommandType.plan, run_id="run-abc123")
        assert cmd.command_type == CommandType.plan
        assert cmd.run_id == "run-abc123"
        assert cmd.version == CONTRACT_VERSION
        assert cmd.payload == {}
        assert cmd.timeout_s == 300
        assert cmd.correlation_id is None

    def test_full_construction(self) -> None:
        cmd = RunCommand(
            command_type=CommandType.implement,
            run_id="run-xyz",
            payload={"issue_key": "PROJ-42", "repo": "my-repo"},
            timeout_s=600,
            correlation_id="corr-1",
        )
        assert cmd.payload["issue_key"] == "PROJ-42"
        assert cmd.timeout_s == 600
        assert cmd.correlation_id == "corr-1"

    def test_serialization_roundtrip(self) -> None:
        cmd = RunCommand(
            command_type=CommandType.validate,
            run_id="run-rt",
            payload={"check": True},
        )
        raw = to_json(cmd)
        restored = from_json(raw, RunCommand)
        assert isinstance(restored, RunCommand)
        assert restored.command_type == cmd.command_type
        assert restored.run_id == cmd.run_id
        assert restored.payload == cmd.payload

    def test_extra_fields_preserved(self) -> None:
        raw = json.dumps(
            {
                "command_type": "plan",
                "run_id": "run-extra",
                "version": CONTRACT_VERSION,
                "future_field": "hello",
            }
        )
        cmd = from_json(raw, RunCommand)
        assert cmd.model_extra.get("future_field") == "hello"

    def test_missing_version_gets_default(self) -> None:
        raw = json.dumps({"command_type": "build", "run_id": "run-noversion"})
        cmd = from_json(raw, RunCommand)
        assert cmd.version == CONTRACT_VERSION

    def test_missing_optional_fields_use_defaults(self) -> None:
        raw = json.dumps(
            {
                "command_type": "test",
                "run_id": "run-defaults",
                "version": CONTRACT_VERSION,
            }
        )
        cmd = from_json(raw, RunCommand)
        assert cmd.payload == {}
        assert cmd.timeout_s == 300
        assert cmd.correlation_id is None


# ── RunEvent ───────────────────────────────────────────────────────────────


class TestRunEvent:
    def test_minimal_construction(self) -> None:
        evt = RunEvent(event_type=EventType.started, run_id="run-e1")
        assert evt.event_type == EventType.started
        assert evt.source_stack == WorkerStack.python
        assert evt.error is None

    def test_error_event(self) -> None:
        evt = RunEvent(
            event_type=EventType.failed,
            run_id="run-e2",
            source_stack=WorkerStack.go,
            error="build failed: exit code 1",
        )
        assert evt.error == "build failed: exit code 1"
        assert evt.source_stack == WorkerStack.go

    def test_serialization_roundtrip(self) -> None:
        evt = RunEvent(
            event_type=EventType.completed,
            run_id="run-e3",
            data={"artifacts": ["report.json"]},
            source_stack=WorkerStack.rust,
        )
        raw = to_json(evt)
        restored = from_json(raw, RunEvent)
        assert isinstance(restored, RunEvent)
        assert restored.event_type == evt.event_type
        assert restored.data == evt.data
        assert restored.source_stack == WorkerStack.rust

    def test_backwards_compat_missing_source_stack(self) -> None:
        raw = json.dumps(
            {
                "event_type": "progress",
                "run_id": "run-compat",
                "version": CONTRACT_VERSION,
            }
        )
        evt = from_json(raw, RunEvent)
        assert evt.source_stack == WorkerStack.python

    def test_extra_fields_preserved(self) -> None:
        raw = json.dumps(
            {
                "event_type": "heartbeat",
                "run_id": "run-hb",
                "version": CONTRACT_VERSION,
                "custom_metric": 42,
            }
        )
        evt = from_json(raw, RunEvent)
        assert evt.model_extra.get("custom_metric") == 42


# ── WorkerCapability ───────────────────────────────────────────────────────


class TestWorkerCapability:
    def test_minimal(self) -> None:
        cap = WorkerCapability(worker_id="w1", stack=WorkerStack.node)
        assert cap.supported_commands == []
        assert cap.max_concurrency == 1

    def test_full(self) -> None:
        cap = WorkerCapability(
            worker_id="go-builder",
            stack=WorkerStack.go,
            supported_commands=[CommandType.build, CommandType.test],
            max_concurrency=4,
            metadata={"version": "1.21"},
        )
        assert CommandType.build in cap.supported_commands
        assert cap.max_concurrency == 4

    def test_serialization_roundtrip(self) -> None:
        cap = WorkerCapability(
            worker_id="rs-1",
            stack=WorkerStack.rust,
            supported_commands=[CommandType.lint],
        )
        raw = to_json(cap)
        restored = from_json(raw, WorkerCapability)
        assert isinstance(restored, WorkerCapability)
        assert restored.worker_id == "rs-1"
        assert restored.stack == WorkerStack.rust


# ── ControlPlaneContract ──────────────────────────────────────────────────


class TestControlPlaneContract:
    def test_python_owned_apis(self) -> None:
        expected = {
            "cli",
            "api_server",
            "workspace_loader",
            "planning",
            "quality_gates",
            "operational_memory",
            "pr_publishing",
        }
        assert set(ControlPlaneContract.PYTHON_OWNED_APIS) == expected

    def test_is_python_owned(self) -> None:
        assert ControlPlaneContract.is_python_owned("planning") is True
        assert ControlPlaneContract.is_python_owned("unknown") is False

    def test_lifecycle_commands(self) -> None:
        cmds = ControlPlaneContract.lifecycle_commands()
        assert CommandType.cancel in cmds
        assert CommandType.resume in cmds
        assert CommandType.inspect in cmds

    def test_worker_lifecycle_phases(self) -> None:
        assert "start" in ControlPlaneContract.WORKER_LIFECYCLE
        assert "monitor" in ControlPlaneContract.WORKER_LIFECYCLE
        assert "cancel" in ControlPlaneContract.WORKER_LIFECYCLE
        assert "resume" in ControlPlaneContract.WORKER_LIFECYCLE


# ── Cross-cutting ─────────────────────────────────────────────────────────


class TestEnums:
    def test_command_type_values(self) -> None:
        assert len(CommandType) == 11

    def test_event_type_values(self) -> None:
        assert len(EventType) == 9

    def test_worker_stack_values(self) -> None:
        assert set(WorkerStack) == {
            WorkerStack.python,
            WorkerStack.go,
            WorkerStack.rust,
            WorkerStack.node,
        }


class TestFromJsonEdgeCases:
    def test_bytes_input(self) -> None:
        raw = json.dumps(
            {"command_type": "cancel", "run_id": "run-bytes", "version": CONTRACT_VERSION}
        ).encode()
        cmd = from_json(raw, RunCommand)
        assert cmd.run_id == "run-bytes"

    def test_invalid_command_type_raises(self) -> None:
        raw = json.dumps(
            {"command_type": "nonexistent", "run_id": "run-bad", "version": CONTRACT_VERSION}
        )
        with pytest.raises(ValueError):
            from_json(raw, RunCommand)

    def test_missing_required_field_raises(self) -> None:
        raw = json.dumps({"command_type": "plan", "version": CONTRACT_VERSION})
        with pytest.raises(ValueError):
            from_json(raw, RunCommand)
