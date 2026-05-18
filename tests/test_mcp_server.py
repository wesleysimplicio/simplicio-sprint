"""Tests for sendsprint/mcp/server.py (Sprint 3 issue #11)."""

from __future__ import annotations

import io
import json
from pathlib import Path

from sendsprint.mcp import McpServer, McpTool, build_default_server
from sendsprint.mcp.server import _read_message, serve_stdio


def _request(method: str, *, rpc_id: int = 1, params: dict | None = None) -> dict:
    req: dict = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        req["params"] = params
    return req


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
            f"Content-Length: {len(body)}\r\nContent-Type: application/json\r\n\r\n".encode()
            + body
        )
        payload = _read_message(io.BytesIO(frame))
        assert payload is not None
        assert payload["method"] == "initialize"

    def test_serve_stdio_writes_framed_response(self) -> None:
        request_body = b'{"jsonrpc":"2.0","id":1,"method":"initialize"}'
        request = (
            (
                f"Content-Length: {len(request_body)}\r\n"
                "Content-Type: application/json\r\n\r\n"
            ).encode()
            + request_body
        )
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
            (
                f"Content-Length: {len(request_body)}\r\n"
                "Content-Type: application/json\r\n\r\n"
            ).encode()
            + request_body
        )
        output = io.BytesIO()
        rc = serve_stdio(instream=io.BytesIO(request), outstream=output)
        assert rc == 0
        assert output.getvalue() == b""
