# ADR-008: Keep the SendSprint MCP server on a stable JSON-RPC 2.0 stdio contract

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-05-18 |
| Deciders | wesleysimplicio |
| Supersedes | — |

---

## Context

Sprint 3 adds a new requirement for SendSprint: the project should not only consume MCP servers, it should also expose its own deterministic capabilities as an MCP tool.

The repository already had:

- MCP-friendly business operations such as tech detection and architecture inspection.
- A lightweight `McpServer` implementation in `sendsprint/mcp/server.py`.
- Tests for the JSON-RPC tool registry and handler dispatch.

What was still undecided was the transport contract:

- whether to depend on an upstream Python MCP SDK that is still moving quickly;
- whether to expose the server only as an internal module or as a CLI command;
- how to keep the surface stable for Claude Code and other agent hosts.

Related prior decisions:

- ADR-002 (`multi-transport`) already treats MCP as a first-class integration surface.
- ADR-004 (`worktree isolation`) keeps concurrent delivery safe, so MCP tools must remain deterministic and side-effect aware.

---

## Decision

SendSprint will expose its MCP mode as a stdio JSON-RPC 2.0 server with explicit `Content-Length` framing, implemented in-repo and surfaced through `sendsprint mcp-serve`.

Implementation rules:

1. The transport stays SDK-free for now; SendSprint owns the framing loop in `sendsprint/mcp/server.py`.
2. The CLI command `sendsprint mcp-serve` is the canonical entrypoint for agent hosts.
3. The default toolset stays intentionally small and deterministic:
   - `sendsprint_detect_tech`
   - `sendsprint_check_architecture`
   - `sendsprint_version`
4. Notifications do not emit responses; tool failures return JSON-RPC errors or `isError=true` content when appropriate.
5. Future tool additions must preserve the same framed stdio contract instead of introducing a second MCP transport path.

---

## Consequences

### Positive

- Claude Code and similar hosts can launch SendSprint directly as an MCP server with a stable command.
- The project avoids lock-in to an unstable Python MCP SDK while still honoring the protocol expected by current clients.
- The test surface stays cheap: framed request/response behavior is covered locally without subprocess or network dependencies.

### Negative

- SendSprint owns a small amount of protocol plumbing instead of delegating it to an upstream package.
- If the upstream MCP protocol changes materially, this transport layer will need explicit maintenance.
- The first release intentionally ships a narrow toolset, so broader MCP coverage still requires future issues.

### Neutral

- Azure DevOps MCP installation remains a separate concern; this ADR covers only the SendSprint server itself.

---

## Alternatives considered

### Use an upstream Python MCP SDK now

- Rejected because the SDK surface is still moving, while SendSprint needs a small stable contract today.

### Keep MCP support as an internal module only

- Rejected because the sprint acceptance explicitly requires a functional `sendsprint mcp-serve` entrypoint for agent hosts.

### Expose line-delimited JSON without MCP framing

- Rejected because Claude Code and other MCP consumers expect framed stdio messages, not ad hoc newline protocols.

---

## Review trigger

- Revisit when the upstream Python MCP SDK stabilizes enough to replace the custom framing loop safely.
- Revisit if new MCP clients require additional capabilities beyond `tools/list` and `tools/call`.

---

## Links

- Issue: https://github.com/wesleysimplicio/SendSprint/issues/18
- Related issues: https://github.com/wesleysimplicio/SendSprint/issues/11, https://github.com/wesleysimplicio/SendSprint/issues/12
- Related ADRs: [ADR-002](./ADR-002-multi-transport.md), [ADR-004](./ADR-004-worktree-isolation.md)
