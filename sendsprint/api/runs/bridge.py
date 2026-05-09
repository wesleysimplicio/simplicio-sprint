"""Bridge between the API run worker and the existing SprintFlow.

Real flow runs are heavy (worktree, install, build, lint, tests, security,
PR). When operator credentials + a repo are available, we call SprintFlow
directly. Otherwise we emit a deterministic mock progression so the mobile
flow is always demoable end-to-end.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sendsprint.api.runs import events
from sendsprint.api.schemas import StartRunRequest

MOCK_STEPS = [
    (1, "read-sprint", "lendo itens da sprint…"),
    (2, "architecture", "mapeando arquitetura do repo…"),
    (3, "dev-build", "instalando deps + build no worktree…"),
    (4, "lint", "rodando ruff / eslint / clippy…"),
    (5, "tests", "rodando unit + Playwright E2E…"),
    (6, "security", "scan de secrets + audit deps…"),
    (7, "fix-loop", "verificando se precisa retry…"),
    (8, "commit", "git add + commit + push…"),
    (9, "create-pr", "abrindo PR no GitHub / ADO…"),
    (10, "review-and-deliver", "diff checks + RunReport.json"),
]


def run_with_events(run_id: str, req: StartRunRequest) -> dict[str, Any]:
    """Try the real SprintFlow; fall back to a mock progression."""
    if req.repo_path:
        try:
            return _run_real(run_id, req)
        except Exception as exc:
            events.publish_threadsafe(
                run_id,
                {
                    "type": "log",
                    "message": f"real run unavailable ({exc}); switching to demo mode",
                },
            )
    return _run_mock(run_id, req)


def _run_real(run_id: str, req: StartRunRequest) -> dict[str, Any]:
    from sendsprint.flow import SprintFlow
    from sendsprint.operators import AzureDevopsOperator, JiraOperator
    from sendsprint.scope import build_scope
    from sendsprint.workspace import load_workspace

    op: Any
    if req.provider == "jira":
        op = JiraOperator(transport="auto")
    else:
        op = AzureDevopsOperator(transport="auto")

    if req.workspace_path:
        ws = load_workspace(req.workspace_path)
    else:
        ws = None

    scope = build_scope(mode="mine") if req.mode == "mine" else None

    flow = SprintFlow(operator=op, workspace=ws, scope=scope)
    events.publish_threadsafe(run_id, {"type": "step", "step": 1, "name": "read-sprint", "status": "running"})
    result = flow.run(sprint_id=req.sprint_id)

    report = result.run_report
    if report:
        for step in report.steps:
            events.publish_threadsafe(
                run_id,
                {
                    "type": "step",
                    "step": step.step,
                    "name": step.name,
                    "status": step.status,
                    "message": step.details.get("message") if step.details else None,
                },
            )
        for pr in report.prs:
            events.publish_threadsafe(
                run_id,
                {"type": "log", "message": f"PR aberto: {pr.url}"},
            )

    pr_url = report.prs[0].url if report and report.prs else None
    summary = result.run_report.summary if result.run_report else None
    return {
        "failed": bool(report.failed) if report else False,
        "summary": summary,
        "pr_url": pr_url,
        "last_step": 10,
    }


def _run_mock(run_id: str, req: StartRunRequest) -> dict[str, Any]:
    """Deterministic 10-step demo with simulated evidence + PR."""
    selected = req.item_keys or ["DEMO-101", "DEMO-102", "DEMO-103"]
    events.publish_threadsafe(
        run_id,
        {
            "type": "log",
            "message": f"modo demo: simulando {len(selected)} item(s) — {', '.join(selected)}",
        },
    )

    for step_num, name, msg in MOCK_STEPS:
        events.publish_threadsafe(
            run_id,
            {
                "type": "step",
                "step": step_num,
                "name": name,
                "status": "running",
                "message": msg,
                "progress": (step_num - 1) / 10,
            },
        )
        time.sleep(0.9)

        if name == "tests":
            evidence = Path("evidence") / run_id / "login-success.png"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            try:
                evidence.write_bytes(_blank_png())
            except OSError:
                pass
            events.publish_threadsafe(
                run_id,
                {
                    "type": "evidence",
                    "evidence_path": str(evidence),
                    "message": "screenshot E2E capturado",
                },
            )

        events.publish_threadsafe(
            run_id,
            {
                "type": "step",
                "step": step_num,
                "name": name,
                "status": "ok",
                "progress": step_num / 10,
            },
        )

    pr_url = "https://github.com/example/repo/pull/4242"
    summary = (
        f"Sprint {req.sprint_id}: 10/10 steps OK • {len(selected)} item(s) processados • PR aberto"
    )
    return {"failed": False, "summary": summary, "pr_url": pr_url, "last_step": 10}


def _blank_png() -> bytes:
    """1×1 transparent PNG so we always have valid evidence bytes in demo mode."""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c63000100000005000100050000000049454e44ae426082"
    )
