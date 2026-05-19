"""Tests for sendsprint/mcp/server.py (Sprint 3 issue #11)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

from sendsprint.mcp import McpServer, McpTool, build_default_server
from sendsprint.mcp.server import _read_message, serve_stdio
from sendsprint.yool.catalog_v2 import yool_hash, yool_slots


def _request(method: str, *, rpc_id: int = 1, params: dict | None = None) -> dict:
    req: dict = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        req["params"] = params
    return req


def _write_catalog(tmp_path: Path, yool_id: str = "agent.codex.plan") -> None:
    h = yool_hash(yool_id)
    target = tmp_path / ".catalog" / "agents.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "meta": {"count": 1},
                "flat": {
                    yool_id: {
                        "hash": f"{h:030b}",
                        "hash_hex": f"{h:08x}",
                        "slots": yool_slots(h),
                        "tuple": {
                            "authority": "codex",
                            "lane": "dev",
                            "description": "Plan work",
                            "guardrails": {
                                "cpu_quota_pct": 60,
                                "disk_quota_mb": 100,
                                "timeout_s": 300,
                            },
                        },
                    }
                },
                "trie": {},
            }
        ),
        encoding="utf-8",
    )


class TestHandshake:
    def test_initialize_returns_protocol_version(self) -> None:
        server = build_default_server()
        resp = server.handle(_request("initialize"))
        assert resp is not None
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert resp["result"]["serverInfo"]["name"] == "sendsprint"

    def test_initialized_notification_returns_none(self) -> None:
        server = build_default_server()
        resp = server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert resp is None


class TestToolsList:
    def test_lists_default_tools(self) -> None:
        server = build_default_server()
        resp = server.handle(_request("tools/list"))
        assert resp is not None
        names = [t["name"] for t in resp["result"]["tools"]]
        assert "sendsprint_detect_tech" in names
        assert "sendsprint_version" in names
        assert "sendsprint_get_run_status" in names

    def test_each_tool_has_schema(self) -> None:
        server = build_default_server()
        resp = server.handle(_request("tools/list"))
        for tool in resp["result"]["tools"]:
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"


class TestToolsCall:
    def test_version_call_returns_version(self) -> None:
        server = build_default_server()
        resp = server.handle(
            _request(
                "tools/call",
                params={"name": "sendsprint_version", "arguments": {}},
            )
        )
        assert resp["result"]["isError"] is False
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert "version" in payload

    def test_detect_tech_call(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"dependencies":{"react":"^18.0.0"}}')
        server = build_default_server()
        resp = server.handle(
            _request(
                "tools/call",
                params={
                    "name": "sendsprint_detect_tech",
                    "arguments": {"repo": str(tmp_path)},
                },
            )
        )
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert "react" in payload["techs"]

    def test_detect_tech_missing_arg_is_isError(self) -> None:
        server = build_default_server()
        resp = server.handle(
            _request("tools/call", params={"name": "sendsprint_detect_tech", "arguments": {}})
        )
        # Standard JSON-RPC error path (-32603) since handler raises ValueError.
        assert "error" in resp
        assert resp["error"]["code"] == -32603

    def test_unknown_tool_returns_jsonrpc_error(self) -> None:
        server = build_default_server()
        resp = server.handle(_request("tools/call", params={"name": "nope", "arguments": {}}))
        assert resp["error"]["code"] == -32601
        assert "unknown tool" in resp["error"]["message"]

    def test_run_status_tool_returns_agent_snapshot(self) -> None:
        from sendsprint.api.runs import manager

        req = {
            "provider": "jira",
            "sprint_id": "123",
            "mode": "selected",
            "item_keys": ["APP-9"],
            "repo_path": None,
            "workspace_path": None,
            "dry_run": False,
            "resume": True,
            "run_id": None,
        }
        status = manager.start_run(SimpleNamespace(**req))
        server = build_default_server()
        resp = server.handle(
            _request(
                "tools/call",
                params={
                    "name": "sendsprint_get_run_status",
                    "arguments": {"run_id": status.run_id},
                },
            )
        )
        assert resp is not None
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload["run_id"] == status.run_id
        assert payload["sprint_id"] == "123"

    def test_snapshot_dispatch_and_inspect_tools(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        _write_catalog(tmp_path)
        server = build_default_server()

        dispatch = server.handle(
            _request(
                "tools/call",
                params={
                    "name": "sendsprint_dispatch",
                    "arguments": {"yool_id": "agent.codex.plan", "payload": {"story": "APP-2"}},
                },
            )
        )
        assert dispatch is not None
        dispatch_payload = json.loads(dispatch["result"]["content"][0]["text"])
        run_id = dispatch_payload["run_id"]

        inspect = server.handle(
            _request(
                "tools/call",
                params={"name": "sendsprint_inspect", "arguments": {"run_id": run_id}},
            )
        )
        assert inspect is not None
        inspect_payload = json.loads(inspect["result"]["content"][0]["text"])
        assert inspect_payload["run_id"] == run_id
        assert inspect_payload["tuples"][0]["yool_id"] == "agent.codex.plan"

        snapshot = server.handle(
            _request(
                "tools/call",
                params={"name": "sendsprint_snapshot", "arguments": {"limit": 1}},
            )
        )
        assert snapshot is not None
        snapshot_payload = json.loads(snapshot["result"]["content"][0]["text"])
        assert "catalog" in snapshot_payload
        assert snapshot_payload["recent_runs"][0]["run_id"] == run_id


class TestUnknownMethod:
    def test_returns_method_not_found(self) -> None:
        server = build_default_server()
        resp = server.handle(_request("totally_made_up"))
        assert resp["error"]["code"] == -32601


class TestCustomTool:
    def test_register_and_call_custom_tool(self) -> None:
        server = McpServer()
        server.register(
            McpTool(
                name="echo",
                description="Echo back",
                input_schema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
                handler=lambda args: {"echoed": args["text"]},
            )
        )
        resp = server.handle(
            _request(
                "tools/call",
                params={"name": "echo", "arguments": {"text": "hi"}},
            )
        )
        payload = json.loads(resp["result"]["content"][0]["text"])
        assert payload == {"echoed": "hi"}


class TestStdioTransport:
    def test_read_message_parses_content_length_frame(self) -> None:
        body = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}'
        frame = (
            f"Content-Length: {len(body)}\r\nContent-Type: application/json\r\n\r\n".encode() + body
        )
        payload = _read_message(io.BytesIO(frame))
        assert payload is not None
        assert payload["method"] == "initialize"

    def test_serve_stdio_writes_framed_response(self) -> None:
        request_body = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}'
        request = (
            f"Content-Length: {len(request_body)}\r\nContent-Type: application/json\r\n\r\n"
        ).encode() + request_body
        output = io.BytesIO()
        rc = serve_stdio(instream=io.BytesIO(request), outstream=output)
        assert rc == 0
        written = output.getvalue()
        assert b"Content-Length:" in written
        _, body = written.split(b"\r\n\r\n", 1)
        payload = json.loads(body.decode("utf-8"))
        assert payload["result"]["protocolVersion"] == "2024-11-05"

    def test_serve_stdio_skips_notification_response(self) -> None:
        request_body = b'{"jsonrpc":"2.0","method":"notifications/initialized"}'
        request = (
            f"Content-Length: {len(request_body)}\r\nContent-Type: application/json\r\n\r\n"
        ).encode() + request_body
        output = io.BytesIO()
        rc = serve_stdio(instream=io.BytesIO(request), outstream=output)
        assert rc == 0
        assert output.getvalue() == b""
