"""SendSprint MCP server (Sprint 3 issue #11).

Lightweight JSON-RPC 2.0 dispatcher that exposes SendSprint's deterministic
operations as MCP tools. Designed so a stdio loop in `cli.py` only needs to
forward JSON-RPC frames to ``McpServer.handle``.

The implementation is intentionally SDK-free — `mcp` Python SDK schema
upstream is still in flux (per ADR-008), and tests must not require
network or process spawning. The handshake and tool schemas follow MCP
spec 2024-11-05 (the version Claude Code currently consumes).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from .. import __version__ as SENDSPRINT_VERSION
from ..tech import detect_tech

PROTOCOL_VERSION = "2024-11-05"
HEADER_SEPARATOR = b"\r\n\r\n"


@dataclass
class McpTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]

    def to_listing(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class McpServer:
    name: str = "sendsprint"
    version: str = SENDSPRINT_VERSION
    tools: dict[str, McpTool] = field(default_factory=dict)

    def register(self, tool: McpTool) -> None:
        self.tools[tool.name] = tool

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        rpc_id = request.get("id")
        params = request.get("params") or {}

        if method == "initialize":
            return self._success(
                rpc_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "serverInfo": {"name": self.name, "version": self.version},
                    "capabilities": {"tools": {}},
                },
            )
        if method == "notifications/initialized":
            return None  # notifications don't get a response
        if method == "tools/list":
            return self._success(rpc_id, {"tools": [t.to_listing() for t in self.tools.values()]})
        if method == "tools/call":
            name = params.get("name") or ""
            arguments = params.get("arguments") or {}
            if not name:
                return self._error(rpc_id, -32602, "missing tool name")
            tool = self.tools.get(name)
            if tool is None:
                return self._error(rpc_id, -32601, f"unknown tool: {name}")
            try:
                value = tool.handler(arguments)
            except _CredentialError as exc:
                return self._success(
                    rpc_id,
                    {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                )
            except Exception as exc:  # noqa: BLE001 - return generic to the client
                return self._error(rpc_id, -32603, f"tool execution failed: {exc}")
            return self._success(
                rpc_id,
                {
                    "content": [
                        {"type": "text", "text": _serialize(value)},
                    ],
                    "isError": False,
                },
            )

        return self._error(rpc_id, -32601, f"method not found: {method}")

    @staticmethod
    def _success(rpc_id: object, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}

    @staticmethod
    def _error(rpc_id: object, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": code, "message": message},
        }


class _CredentialError(RuntimeError):
    """Surface credential issues without leaking stack traces to the client."""


# ---------------------------------------------------------------------------
# Stdio transport helpers
# ---------------------------------------------------------------------------


def serve_stdio(
    server: McpServer | None = None,
    *,
    instream: BinaryIO,
    outstream: BinaryIO,
) -> int:
    """Serve MCP JSON-RPC over stdio using Content-Length framed messages."""
    active = server or build_default_server()
    while True:
        request = _read_message(instream)
        if request is None:
            return 0
        response = active.handle(request)
        if response is not None:
            _write_message(outstream, response)


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    headers = _read_headers(stream)
    if headers is None:
        return None

    content_length = headers.get("content-length")
    if content_length is None:
        raise ValueError("missing Content-Length header")

    try:
        length = int(content_length)
    except ValueError as exc:  # pragma: no cover - defensive parse guard
        raise ValueError(f"invalid Content-Length: {content_length!r}") from exc

    payload = stream.read(length)
    if len(payload) != length:
        raise ValueError("incomplete MCP payload")
    return json.loads(payload.decode("utf-8"))


def _read_headers(stream: BinaryIO) -> dict[str, str] | None:
    buffer = bytearray()
    while HEADER_SEPARATOR not in buffer:
        chunk = stream.read(1)
        if chunk == b"":
            if not buffer:
                return None
            raise ValueError("unexpected EOF while reading MCP headers")
        buffer.extend(chunk)

    raw_headers = bytes(buffer).split(HEADER_SEPARATOR, 1)[0].decode("utf-8")
    headers: dict[str, str] = {}
    for line in raw_headers.split("\r\n"):
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"invalid MCP header line: {line!r}")
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _write_message(stream: BinaryIO, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    headers = f"Content-Length: {len(body)}\r\nContent-Type: application/json\r\n\r\n".encode()
    stream.write(headers)
    stream.write(body)
    stream.flush()


# ---------------------------------------------------------------------------
# Default toolset
# ---------------------------------------------------------------------------


def build_default_server() -> McpServer:
    server = McpServer()
    server.register(_detect_tech_tool())
    server.register(_check_architecture_tool())
    server.register(_version_tool())
    return server


def _detect_tech_tool() -> McpTool:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        repo = args.get("repo")
        if not repo:
            raise ValueError("missing required arg: repo")
        fp = detect_tech(Path(repo))
        return {
            "techs": fp.techs,
            "roles": fp.roles,
            "package_managers": fp.package_managers,
            "signals": fp.signals,
        }

    return McpTool(
        name="sendsprint_detect_tech",
        description=(
            "Inspect a repository's filesystem markers and return a "
            "TechFingerprint (techs, roles, package_managers, signals)."
        ),
        input_schema={
            "type": "object",
            "properties": {"repo": {"type": "string", "description": "Absolute repo path"}},
            "required": ["repo"],
        },
        handler=handler,
    )


def _check_architecture_tool() -> McpTool:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        repo = args.get("repo")
        if not repo:
            raise ValueError("missing required arg: repo")
        # Import lazily so the MCP module can be imported without the full graph.
        from ..architecture.mapper import ArchitectureMapper

        result = ArchitectureMapper().inspect(Path(repo))
        return result.model_dump() if hasattr(result, "model_dump") else dict(result)

    return McpTool(
        name="sendsprint_check_architecture",
        description="Score a repo against the SendSprint architecture baseline.",
        input_schema={
            "type": "object",
            "properties": {"repo": {"type": "string"}},
            "required": ["repo"],
        },
        handler=handler,
    )


def _version_tool() -> McpTool:
    def handler(args: dict[str, Any]) -> dict[str, Any]:
        from .. import __version__

        return {"version": __version__}

    return McpTool(
        name="sendsprint_version",
        description="Return the installed SendSprint version.",
        input_schema={"type": "object", "properties": {}},
        handler=handler,
    )


def _serialize(value: object) -> str:
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    try:
        return json.dumps(value, default=str, indent=2)
    except (TypeError, ValueError):
        return str(value)
