"""Tests for sendsprint/dashboard_spec.py — schema validation and event types.

Covers: SSEEventType completeness, SSEEventPayload validation,
DashboardEventProtocol invariants, NodeDashboardSpec contracts,
PlaywrightLaneSpec isolation rules.

Issue: #109
"""

from __future__ import annotations

import pytest

from sendsprint.dashboard_spec import (
    DashboardEventProtocol,
    NodeDashboardScope,
    NodeDashboardSpec,
    PlaywrightEvidenceKind,
    PlaywrightLaneSpec,
    SSEEventPayload,
    SSEEventType,
)

# ---------------------------------------------------------------------------
# SSEEventType
# ---------------------------------------------------------------------------


class TestSSEEventType:
    def test_all_event_types_present(self):
        expected = {
            "hello",
            "step",
            "log",
            "evidence",
            "loop",
            "regression",
            "summary",
            "done",
            "error",
            "agent_state",
            "operator_chat",
            "keepalive",
        }
        assert {e.value for e in SSEEventType} == expected

    def test_terminal_events(self):
        """done and error are the only terminal events."""
        terminal = {"done", "error"}
        proto = DashboardEventProtocol()
        assert set(proto.terminal_events) == terminal

    def test_enum_string_values(self):
        for member in SSEEventType:
            assert isinstance(member.value, str)
            assert member.value == member.name


# ---------------------------------------------------------------------------
# SSEEventPayload
# ---------------------------------------------------------------------------


class TestSSEEventPayload:
    def test_minimal_payload(self):
        p = SSEEventPayload(type=SSEEventType.hello, run_id="run-abc123")
        assert p.type == SSEEventType.hello
        assert p.run_id == "run-abc123"
        assert p.step is None
        assert p.progress is None

    def test_step_payload(self):
        p = SSEEventPayload(
            type=SSEEventType.step,
            run_id="run-1",
            step=3,
            name="tests",
            status="running",
            progress=0.6,
        )
        assert p.step == 3
        assert p.name == "tests"
        assert p.progress == 0.6

    def test_evidence_payload(self):
        p = SSEEventPayload(
            type=SSEEventType.evidence,
            run_id="run-1",
            evidence_path="evidence/run-1/screenshot.png",
            evidence_label="Login page",
        )
        assert p.evidence_path == "evidence/run-1/screenshot.png"
        assert p.evidence_label == "Login page"

    def test_agent_state_payload(self):
        p = SSEEventPayload(
            type=SSEEventType.agent_state,
            run_id="run-1",
            agent_name="codex",
            agent_status="implementing",
        )
        assert p.agent_name == "codex"
        assert p.agent_status == "implementing"

    def test_operator_chat_payload(self):
        p = SSEEventPayload(
            type=SSEEventType.operator_chat,
            run_id="run-1",
            chat_message="Approve deploy?",
            chat_sender="claude",
        )
        assert p.chat_message == "Approve deploy?"
        assert p.chat_sender == "claude"

    def test_extra_fields_allowed(self):
        """Dashboard payloads allow extra fields for forward compatibility."""
        p = SSEEventPayload(
            type=SSEEventType.log,
            run_id="run-1",
            message="hello",
            future_field="new_data",
        )
        assert p.model_extra.get("future_field") == "new_data"

    def test_serialization_roundtrip(self):
        p = SSEEventPayload(
            type=SSEEventType.done,
            run_id="run-x",
            summary="All tasks delivered",
            pr_url="https://github.com/org/repo/pull/42",
            failed=False,
        )
        raw = p.model_dump_json()
        restored = SSEEventPayload.model_validate_json(raw)
        assert restored.type == SSEEventType.done
        assert restored.summary == "All tasks delivered"
        assert restored.pr_url == "https://github.com/org/repo/pull/42"
        assert restored.failed is False


# ---------------------------------------------------------------------------
# DashboardEventProtocol
# ---------------------------------------------------------------------------


class TestDashboardEventProtocol:
    def test_defaults(self):
        proto = DashboardEventProtocol()
        assert proto.transport == "sse"
        assert proto.keepalive_interval_s == 30
        assert proto.endpoint_pattern == "/runs/{run_id}/events"

    def test_event_types_match_enum(self):
        proto = DashboardEventProtocol()
        assert set(proto.event_types) == {e.value for e in SSEEventType}

    def test_frozen(self):
        proto = DashboardEventProtocol()
        with pytest.raises(ValueError):
            proto.transport = "ws"  # type: ignore[misc]

    def test_ordering_guarantee_documented(self):
        proto = DashboardEventProtocol()
        assert "causal order" in proto.ordering_guarantee

    def test_reconnect_advice_documented(self):
        proto = DashboardEventProtocol()
        assert "backoff" in proto.reconnect_advice
        assert "poll" in proto.reconnect_advice


# ---------------------------------------------------------------------------
# NodeDashboardSpec
# ---------------------------------------------------------------------------


class TestNodeDashboardSpec:
    def test_defaults(self):
        spec = NodeDashboardSpec()
        assert spec.spec_version == "1.0.0"
        assert "UI" in spec.description or "ui" in spec.description.lower()

    def test_all_scopes_included(self):
        spec = NodeDashboardSpec()
        assert set(spec.allowed_scopes) == set(NodeDashboardScope)

    def test_forbidden_actions_not_empty(self):
        spec = NodeDashboardSpec()
        assert len(spec.forbidden_actions) > 0

    def test_orchestration_is_forbidden(self):
        spec = NodeDashboardSpec()
        assert "own_orchestration" in spec.forbidden_actions

    def test_worker_management_forbidden(self):
        spec = NodeDashboardSpec()
        assert "manage_workers" in spec.forbidden_actions

    def test_quality_gate_evaluation_forbidden(self):
        spec = NodeDashboardSpec()
        assert "evaluate_quality_gates" in spec.forbidden_actions

    def test_consumed_apis_not_empty(self):
        spec = NodeDashboardSpec()
        assert len(spec.consumed_apis) > 0

    def test_consumed_apis_have_required_fields(self):
        spec = NodeDashboardSpec()
        for api in spec.consumed_apis:
            assert "method" in api
            assert "path" in api
            assert "purpose" in api

    def test_consumed_apis_include_sse_endpoint(self):
        spec = NodeDashboardSpec()
        sse_apis = [a for a in spec.consumed_apis if "events" in a["path"]]
        assert len(sse_apis) == 1

    def test_consumed_apis_include_evidence_endpoint(self):
        spec = NodeDashboardSpec()
        evidence_apis = [
            a for a in spec.consumed_apis if "evidence" in a["path"] and "{name}" in a["path"]
        ]
        assert len(evidence_apis) == 1

    def test_has_event_protocol(self):
        spec = NodeDashboardSpec()
        assert isinstance(spec.event_protocol, DashboardEventProtocol)

    def test_frozen(self):
        spec = NodeDashboardSpec()
        with pytest.raises(ValueError):
            spec.spec_version = "2.0.0"  # type: ignore[misc]

    def test_serialization_roundtrip(self):
        spec = NodeDashboardSpec()
        raw = spec.model_dump_json()
        restored = NodeDashboardSpec.model_validate_json(raw)
        assert restored.spec_version == spec.spec_version
        assert len(restored.consumed_apis) == len(spec.consumed_apis)
        assert restored.forbidden_actions == spec.forbidden_actions


# ---------------------------------------------------------------------------
# PlaywrightLaneSpec
# ---------------------------------------------------------------------------


class TestPlaywrightLaneSpec:
    def test_defaults(self):
        spec = PlaywrightLaneSpec()
        assert spec.spec_version == "1.0.0"
        assert "isolated" in spec.description.lower()

    def test_evidence_kinds(self):
        spec = PlaywrightLaneSpec()
        expected = {k.value for k in PlaywrightEvidenceKind}
        actual = {k.value for k in spec.evidence_kinds}
        assert actual == expected

    def test_output_dir_pattern(self):
        spec = PlaywrightLaneSpec()
        assert "{run_id}" in spec.output_dir_pattern

    def test_isolation_rules_not_empty(self):
        spec = PlaywrightLaneSpec()
        assert len(spec.isolation_rules) > 0

    def test_no_python_import_rule(self):
        spec = PlaywrightLaneSpec()
        import_rules = [r for r in spec.isolation_rules if "import" in r.lower()]
        assert len(import_rules) >= 1

    def test_no_run_state_access_rule(self):
        spec = PlaywrightLaneSpec()
        state_rules = [
            r
            for r in spec.isolation_rules
            if "state" in r.lower() and ("read" in r.lower() or "write" in r.lower())
        ]
        assert len(state_rules) >= 1

    def test_evidence_flow_documented(self):
        spec = PlaywrightLaneSpec()
        assert len(spec.evidence_flow) >= 3

    def test_evidence_flow_starts_with_capture(self):
        spec = PlaywrightLaneSpec()
        assert "capture" in spec.evidence_flow[0].lower()

    def test_forbidden_actions_not_empty(self):
        spec = PlaywrightLaneSpec()
        assert len(spec.forbidden_actions) > 0

    def test_quality_gate_evaluation_forbidden(self):
        spec = PlaywrightLaneSpec()
        gate_rules = [
            r for r in spec.forbidden_actions if "quality" in r.lower() and "gate" in r.lower()
        ]
        assert len(gate_rules) >= 1

    def test_frozen(self):
        spec = PlaywrightLaneSpec()
        with pytest.raises(ValueError):
            spec.spec_version = "2.0.0"  # type: ignore[misc]

    def test_serialization_roundtrip(self):
        spec = PlaywrightLaneSpec()
        raw = spec.model_dump_json()
        restored = PlaywrightLaneSpec.model_validate_json(raw)
        assert restored.spec_version == spec.spec_version
        assert restored.evidence_kinds == spec.evidence_kinds
        assert restored.isolation_rules == spec.isolation_rules

    def test_allowed_api_calls_read_only(self):
        spec = PlaywrightLaneSpec()
        for call in spec.allowed_api_calls:
            assert call.startswith("GET"), f"Playwright should only have GET calls: {call}"


# ---------------------------------------------------------------------------
# Cross-spec consistency
# ---------------------------------------------------------------------------


class TestCrossSpecConsistency:
    def test_dashboard_sse_types_match_payload_enum(self):
        """DashboardEventProtocol event_types must match SSEEventType enum."""
        proto = DashboardEventProtocol()
        assert set(proto.event_types) == {e.value for e in SSEEventType}

    def test_dashboard_consumed_apis_cover_evidence(self):
        """Dashboard must consume evidence endpoints that Playwright writes to."""
        spec = NodeDashboardSpec()
        paths = [a["path"] for a in spec.consumed_apis]
        assert any("evidence" in p for p in paths)

    def test_playwright_output_dir_matches_evidence_endpoint(self):
        """Playwright output dir pattern and evidence API path use same run_id."""
        pw = PlaywrightLaneSpec()
        dash = NodeDashboardSpec()
        evidence_apis = [a for a in dash.consumed_apis if "evidence" in a["path"]]
        assert len(evidence_apis) > 0
        # Both reference run_id
        assert "{run_id}" in pw.output_dir_pattern
        for api in evidence_apis:
            assert "{run_id}" in api["path"]
