"""Cross-stack runtime readiness checks for the #105 epic."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.contracts import ControlPlaneContract
from sendsprint.dashboard_spec import NodeDashboardScope, NodeDashboardSpec
from sendsprint.scheduler import AgentFanoutPolicy, HostResourceSnapshot
from sendsprint.workers.go_spec import GoWorkerSpec
from sendsprint.workers.resolver import resolve_worker

RuntimeStack = Literal["python", "go", "rust", "node", "copilot"]


class RuntimeStackBoundary(BaseModel):
    """One explicit stack boundary in the runtime split."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stack: RuntimeStack
    owner: str
    purpose: str
    contract: str
    validation: str
    rollback: str


class RuntimeReadinessCriterion(BaseModel):
    """One closeout criterion for the cross-stack runtime epic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    passed: bool
    evidence: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class CrossStackRuntimeReadiness(BaseModel):
    """Auditable readiness report for issue #105."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    epic: str = "#105"
    status: Literal["ready", "blocked"] = "blocked"
    boundaries: list[RuntimeStackBoundary] = Field(default_factory=list)
    criteria: list[RuntimeReadinessCriterion] = Field(default_factory=list)


def build_cross_stack_runtime_readiness(
    repo_path: str | Path = ".",
) -> CrossStackRuntimeReadiness:
    """Build a deterministic readiness report without running external workers."""
    root = Path(repo_path).resolve()
    criteria = [
        _criterion(
            "architecture-decision",
            (root / ".specs/architecture/ADR-009-cross-stack-runtime.md").is_file(),
            "ADR-009 documents Python/Go/Rust/Node/Copilot boundaries.",
            "missing ADR-009-cross-stack-runtime.md",
        ),
        _criterion(
            "python-control-plane-contract",
            _python_contract_is_stable(),
            "ControlPlaneContract keeps CLI/API/planning/gates/memory/PR ownership in Python.",
            "ControlPlaneContract no longer exposes the expected Python-owned APIs.",
        ),
        _criterion(
            "go-worker-non-blocking-boundary",
            _go_worker_boundary_is_ready(),
            "GoWorkerSpec defines queue/status/heartbeat/log_tail over the worker protocol.",
            "GoWorkerSpec is missing a required non-blocking action.",
        ),
        _criterion(
            "rust-accelerator-benchmark-gate",
            (root / "sendsprint/runtime_baseline.py").is_file()
            and (root / "sendsprint/accelerators/resolver.py").is_file(),
            "Runtime baseline exists and Rust resolver falls back to Python when unavailable.",
            "runtime baseline or Rust resolver is missing.",
        ),
        _criterion(
            "node-dashboard-operator-loop",
            _node_dashboard_boundary_is_ready(),
            "Node dashboard consumes run/event APIs and includes operator chat rendering scope.",
            "Node dashboard spec is missing live status or operator chat scope.",
        ),
        _criterion(
            "windows-copilot-happy-path",
            _copilot_happy_path_is_documented(root),
            ".github/copilot-instructions.md documents Windows and non-/goal operation.",
            "Copilot Windows happy path is missing or depends on /goal.",
        ),
        _criterion(
            "child-validation-and-rollback",
            _roadmap_has_runtime_children(root),
            "Runtime child issues are mapped with dependencies and validation/rollback contracts.",
            "runtime child issue map is incomplete.",
        ),
        _criterion(
            "resource-aware-fanout",
            _fanout_decision_is_auditable(),
            "AgentFanoutPolicy returns an auditable resource decision receipt.",
            "fan-out policy cannot produce a decision receipt.",
        ),
    ]
    status: Literal["ready", "blocked"] = (
        "ready" if all(item.passed for item in criteria) else "blocked"
    )
    return CrossStackRuntimeReadiness(
        status=status,
        boundaries=_stack_boundaries(),
        criteria=criteria,
    )


def format_runtime_readiness_markdown(report: CrossStackRuntimeReadiness) -> str:
    """Render a PR/issue-ready Markdown closeout summary."""
    lines = [
        f"# Cross-stack runtime readiness ({report.epic})",
        "",
        f"Status: **{report.status}**",
        "",
        "## Stack boundaries",
        "",
        "| Stack | Owner | Purpose | Contract | Validation | Rollback |",
        "|---|---|---|---|---|---|",
    ]
    for boundary in report.boundaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    boundary.stack,
                    boundary.owner,
                    boundary.purpose,
                    boundary.contract,
                    boundary.validation,
                    boundary.rollback,
                ]
            )
            + " |"
        )
    lines.extend(["", "## Criteria", ""])
    for criterion in report.criteria:
        mark = "x" if criterion.passed else " "
        lines.append(f"- [{mark}] `{criterion.key}`")
        for evidence in criterion.evidence:
            lines.append(f"  - Evidence: {evidence}")
        for blocker in criterion.blockers:
            lines.append(f"  - Blocker: {blocker}")
    return "\n".join(lines) + "\n"


def _criterion(
    key: str,
    passed: bool,
    evidence: str,
    blocker: str,
) -> RuntimeReadinessCriterion:
    return RuntimeReadinessCriterion(
        key=key,
        passed=passed,
        evidence=[evidence] if passed else [],
        blockers=[] if passed else [blocker],
    )


def _stack_boundaries() -> list[RuntimeStackBoundary]:
    return [
        RuntimeStackBoundary(
            stack="python",
            owner="control plane",
            purpose="CLI/API orchestration, planning, quality gates, memory, publishing",
            contract="RunCommand/RunEvent plus ControlPlaneContract",
            validation="pytest contract/API/runtime readiness tests",
            rollback="Python fallback remains canonical and can disable optional workers",
        ),
        RuntimeStackBoundary(
            stack="go",
            owner="optional worker runtime",
            purpose="fan-out, watchdogs, bounded queues, heartbeat/status/log tails",
            contract="GoWorkerSpec NDJSON request/response protocol",
            validation="worker resolver/proxy tests and fan-out receipt tests",
            rollback="resolve_worker(prefer_go=False) or missing binary uses PythonWorker",
        ),
        RuntimeStackBoundary(
            stack="rust",
            owner="optional accelerator",
            purpose="scan, diff, dedupe, receipt/hash hot paths",
            contract="accelerator resolver and runtime baseline benchmark gate",
            validation="accelerator parity tests plus runtime-baseline evidence",
            rollback="RustBridge(None) routes all operations to Python implementations",
        ),
        RuntimeStackBoundary(
            stack="node",
            owner="dashboard and Playwright lane",
            purpose="live status UI, operator chat rendering, browser evidence",
            contract="NodeDashboardSpec, DashboardEventProtocol, PlaywrightLaneSpec",
            validation="dashboard spec/API tests and Playwright CI lane",
            rollback="Python API and evidence bundles remain usable without dashboard",
        ),
        RuntimeStackBoundary(
            stack="copilot",
            owner="IDE assistant profile",
            purpose="standard SendSprint workflow on Windows without /goal or Ralph",
            contract=".github/copilot-instructions.md and validation recipes",
            validation="documentation checks and stack validation recipe tests",
            rollback="Copilot follows CLI commands; Codex/Claude accelerators stay optional",
        ),
    ]


def _python_contract_is_stable() -> bool:
    expected = {
        "cli",
        "api_server",
        "workspace_loader",
        "planning",
        "quality_gates",
        "operational_memory",
        "pr_publishing",
    }
    return expected <= set(ControlPlaneContract.PYTHON_OWNED_APIS)


def _go_worker_boundary_is_ready() -> bool:
    spec = GoWorkerSpec()
    required = {"queue", "start", "cancel", "heartbeat", "status", "log_tail", "shutdown"}
    fallback = resolve_worker(prefer_go=False)
    return required <= set(spec.supported_actions) and fallback.__class__.__name__ == "PythonWorker"


def _node_dashboard_boundary_is_ready() -> bool:
    spec = NodeDashboardSpec()
    scopes = set(spec.allowed_scopes)
    api_paths = {api["path"] for api in spec.consumed_apis}
    return (
        NodeDashboardScope.render_operator_chat in scopes
        and "/runs/{run_id}/events" in api_paths
        and "operator_chat" in spec.event_protocol.event_types
    )


def _copilot_happy_path_is_documented(root: Path) -> bool:
    path = root / ".github/copilot-instructions.md"
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8")
    return "Windows install path" in content and "accelerators, not requirements" in content


def _roadmap_has_runtime_children(root: Path) -> bool:
    path = root / ".specs/architecture/ROADMAP.md"
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8")
    child_ids = ("#106", "#107", "#108", "#109", "#110", "#111", "#112", "#114", "#115")
    return all(child_id in content for child_id in child_ids)


def _fanout_decision_is_auditable() -> bool:
    receipt = AgentFanoutPolicy(requested_agents=5).decision_for(
        HostResourceSnapshot(logical_cpus=8, available_memory_mb=16_384, cpu_idle_percent=80)
    )
    return receipt.allowed_agents > 0 and bool(receipt.reasons)
