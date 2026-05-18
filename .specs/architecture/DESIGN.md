# SendSprint — System Design

> Bird's-eye architecture. Layers, data flow, concurrency, failure model. Source of truth for `sendsprint/` layout.

---

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│  CLI (Typer)              sendsprint/cli.py                  │
│  ─ run / read-jira / read-ado / detect-tech / check-arch     │
└────────────────┬─────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│  Flow orchestrator        sendsprint/flow/sprint_flow.py    │
│  ─ Runs delivery flow + opt-in hooks, builds RunReport      │
└──┬──────────┬──────────┬──────────┬──────────┬──────────────┘
   │          │          │          │          │
┌──▼──┐   ┌───▼───┐  ┌───▼───┐  ┌───▼───┐  ┌──▼────┐
│Op   │   │Arch   │  │Agents │  │Flow   │  │PR     │
│erat │   │Mapper │  │Dev/   │  │Fix    │  │Creator│
│ors  │   │       │  │Lint/  │  │Loop   │  │Reviewr│
│Jira │   │       │  │Test/  │  │Push   │  │       │
│ADO  │   │       │  │Sec    │  │       │  │       │
└──┬──┘   └───┬───┘  └───┬───┘  └───┬───┘  └──┬────┘
   │          │          │          │         │
┌──▼──────────▼──────────▼──────────▼─────────▼──────────────┐
│  Infra: WorktreeManager · LLM client · httpx · subprocess  │
│  Models (Pydantic v2): Sprint, RunReport, ...              │
└────────────────────────────────────────────────────────────┘
```

---

## Layers (detailed)

| Layer | Module | Responsibility | Depends on |
|-------|--------|----------------|------------|
| 1. CLI | `sendsprint/cli.py` | Typer entry points, arg parsing, exit codes | flow + operators |
| 2. Flow | `sendsprint/flow/` | Delivery orchestration, optional codegen/deploy hooks, fix loop, push, RunReport assembly | all below |
| 3. Operators | `sendsprint/operators/` | Read sprint via Jira/ADO, transport fallback chain | httpx, mcp client, playwright |
| 4. Architecture | `sendsprint/architecture/` | Detect tech, score baseline, optional rebuild | filesystem |
| 5. Agents | `sendsprint/agents/` | DevAgent, LintRunner, TestRunner, SecurityReviewer, PrCreator, PrReviewer | subprocess, gh CLI, ADO REST |
| 6. Infra | `sendsprint/worktree/`, `sendsprint/llm/`, `sendsprint/models/` | Worktree manager, LLM client, Pydantic v2 models | git, anthropic/openai SDKs |

---

## Data flow per run

```
sendsprint run jira 42 --workspace workspace.yaml --scope mine
   │
   ├─ load_workspace(yaml) → Workspace
   ├─ build_scope(mode="mine", email=...) → ScopeConfig
   ├─ JiraOperator(transport="auto").read(sprint_id=42) → Sprint
   │       ├─ try mcp client
   │       ├─ fallback httpx (Jira REST)
   │       └─ fallback playwright (CDP)
   │
   ├─ for repo in workspace.repos:
   │     ArchitectureMapper.map(repo) → score + baseline
   │     with WorktreeManager(repo, branch=f"sprint/{sprint.id}"):
   │         DevAgent.install_and_build()        # step 3
   │         CodeGenerator.generate()            # step 3.5 (opt-in)
   │         LintRunner.run()                    # step 4
   │         TestRunner.run_unit() + run_e2e()   # step 5
   │         SecurityReviewer.scan()             # step 6
   │         while issues and rounds < 3:        # step 7
   │             retry steps 3–6
   │         git commit + push --force-with-lease # step 8
   │         PrCreator.create()                  # step 9
   │         PrReviewer.review_diff()            # step 10
   │         DeployTrigger.run()                 # step 11 (opt-in)
   │
   └─ RunReport.to_json() → report.json
```

---

## Concurrency

- **Per-repo isolation** via `WorktreeManager` (git worktree). Each repo can run in parallel without branch conflicts.
- **Within a repo**: steps run sequentially (3 → 4 → 5 → 6 → 7).
- **Transport fallback**: sequential, never parallel (avoid double-charging API quota).
- **LLM calls**: serialized per step. No concurrent prompts (cost control + budget caps).

> v0.2.x runs repos sequentially. Multi-repo parallelism is on the v0.3 roadmap (`asyncio.gather` over `WorktreeManager` contexts).

---

## Failure model

| Failure | Step | Recovery |
|---------|------|----------|
| Sprint read fails (all transports) | 1 | Abort run, `RunReport.failed=true` |
| Architecture score < 0.6 | 2 | Auto-build baseline, continue |
| Install/build fails | 3 | Retry in fix loop (step 7) |
| Lint fails | 4 | Retry in fix loop |
| Tests fail | 5 | Retry in fix loop |
| Security finding | 6 | **Halt** — never auto-fix (ADR-005) |
| Fix loop > 3 rounds | 7 | Mark `failed=true`, skip push/PR |
| Push rejected | 8 | Abort PR creation, log error |
| PR creation fails | 9 | Log error, RunReport still emitted |
| PR review finds issues | 10 | Flag in report, do NOT auto-comment |
| Deploy webhook fails | 11 | Flag deploy step, keep PR as source of truth |

---

## Extension points

- **New operator** (e.g., GitLab Issues): subclass `BaseOperator`, register in `cli.py` typer group.
- **New stack support**: extend `detect_tech()` heuristics + `LintRunner._STACK_COMMANDS` + `TestRunner._STACK_COMMANDS`.
- **New PR provider**: subclass `BasePrProvider`, switch in `Workspace.pr_provider`.
- **New LLM**: implement `LlmClient` protocol in `sendsprint/llm/client.py`.

---

## See also

- [PATTERNS.md](PATTERNS.md) — code idioms
- [ADR-001-stack.md](ADR-001-stack.md) — Python + Pydantic v2 + Typer choice
- [ADR-002-multi-transport.md](ADR-002-multi-transport.md) — mcp → api → playwright order
- [ADR-003-mock-fallback.md](ADR-003-mock-fallback.md) — three test tiers
- [ADR-004-worktree-isolation.md](ADR-004-worktree-isolation.md) — per-repo branches
- [ADR-005-flag-only-security.md](ADR-005-flag-only-security.md) — never auto-fix security
- [ADR-006-llm-codegen-budgeting.md](ADR-006-llm-codegen-budgeting.md) — opt-in LLM provider and budget policy
- [ADR-007-deploy-callback-idempotency.md](ADR-007-deploy-callback-idempotency.md) — deploy webhook + ticket callback semantics
- [/.specs/product/DOMAIN.md](../product/DOMAIN.md) — entities
- [/AGENTS.md](../../AGENTS.md) — canonical instructions
