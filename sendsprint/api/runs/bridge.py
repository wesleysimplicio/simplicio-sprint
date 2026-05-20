"""Bridge between the API run worker and the existing SprintFlow.

Real flow runs are heavy (worktree, install, build, lint, tests, security,
PR). When operator credentials + a repo are available, we call SprintFlow
directly. Otherwise we emit a deterministic mock progression so the web
flow is always demoable end-to-end — including a regression failure on the
first attempt, the fix loop kicking in, and a passing re-run before commit/PR.
"""

from __future__ import annotations

import contextlib
import shutil
import time
from pathlib import Path
from typing import Any

from sendsprint.api.assets import SCREENSHOTS_DIR
from sendsprint.api.runs import events
from sendsprint.api.schemas import StartRunRequest

MAX_ITERATIONS = 3
STEP_DELAY = 0.45  # seconds between mock step transitions

# Regression failures simulated on the first attempt.
FAILING_TESTS_FIRST_RUN = [
    "test_dashboard.py::test_kpis_render",
    "test_dashboard.py::test_velocity_chart",
    "test_regression.py::test_signup_email_validation",
]


def run_with_events(run_id: str, req: StartRunRequest) -> dict[str, Any]:
    """Try the real SprintFlow; fall back to a mock progression."""
    if req.repo_path or req.workspace_path:
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
    from sendsprint.policy import AutonomyPolicy, parse_autonomy_level
    from sendsprint.scope import build_scope
    from sendsprint.workspace import load_workspace

    op: Any
    if req.provider == "jira":
        op = JiraOperator(transport="auto")
    else:
        op = AzureDevopsOperator(transport="auto")

    ws = load_workspace(req.workspace_path) if req.workspace_path else None
    scope = build_scope(
        mode="mine" if req.mode == "mine" else "all",
        task_keys=req.item_keys or None,
    )

    flow = SprintFlow(
        operator=op,
        workspace=ws,
        scope=scope,
        autonomy_policy=AutonomyPolicy(level=parse_autonomy_level(req.autonomy_level)),
    )
    events.publish_threadsafe(
        run_id, {"type": "step", "step": 1, "name": "read-sprint", "status": "running"}
    )
    if req.provider == "jira":
        result = flow.bootstrap(
            sprint_id=req.sprint_id,
            repo_path=req.repo_path,
            dry_run=req.dry_run,
            resume=req.resume,
            run_id=run_id,
            no_cache=req.no_cache,
        )
    else:
        result = flow.bootstrap(
            iteration_path=req.sprint_id,
            repo_path=req.repo_path,
            dry_run=req.dry_run,
            resume=req.resume,
            run_id=run_id,
            no_cache=req.no_cache,
        )

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

    if result.delivery_plan:
        events.publish_threadsafe(
            run_id,
            {
                "type": "log",
                "message": f"dry-run plan: {result.delivery_plan.summary()}",
            },
        )
    pr_url = report.prs[0].url if report and report.prs else None
    summary = result.run_report.summary if result.run_report else None
    return {
        "failed": bool(report.failed) if report else False,
        "summary": summary,
        "pr_url": pr_url,
        "last_step": 10,
    }


# ---------- mock orchestrator ----------


def _run_mock(run_id: str, req: StartRunRequest) -> dict[str, Any]:
    """Realistic 10-step demo with a fix loop iteration before passing."""
    selected = req.item_keys or ["DEMO-101", "DEMO-102", "DEMO-103"]
    _emit_log(run_id, f"modo demo: simulando {len(selected)} item(s) — {', '.join(selected)}")

    # Steps 1 & 2 — read sprint + map architecture (always pass)
    _do_step(run_id, 1, "read-sprint", "lendo itens da sprint…", progress=0.05)
    _do_step(run_id, 2, "architecture", "score atual: 0.82 ✓", progress=0.12)

    iteration = 1
    pr_url: str | None = None
    failed = False

    while iteration <= MAX_ITERATIONS:
        _emit_loop(run_id, iteration, MAX_ITERATIONS)

        # Steps 3-6 — install/build, lint, tests, security
        _do_step(
            run_id,
            3,
            "dev-build",
            "npm ci + npm run build" if iteration == 1 else "rebuild com patch aplicado",
            progress=0.22 + 0.02 * (iteration - 1),
        )
        _do_step(
            run_id,
            4,
            "lint",
            "ruff check sendsprint/ tests/" if iteration == 1 else "ruff format aplicado",
            progress=0.34 + 0.02 * (iteration - 1),
        )

        # Step 5 — tests + regression
        first_pass = iteration == 1
        _emit_step(run_id, 5, "tests-unit", "running", "pytest tests/ -v", progress=0.44)
        time.sleep(STEP_DELAY)
        _emit_step(run_id, 5, "tests-unit", "ok", "47 passed · 0 failed · 2 skipped", progress=0.48)

        # E2E + regression test phase
        _emit_step(run_id, 5, "tests-e2e", "running", "playwright test — login flow", progress=0.52)
        _emit_evidence(run_id, "login.png", iteration, label="login flow capturado")
        time.sleep(STEP_DELAY)

        _emit_step(
            run_id, 5, "tests-e2e", "running", "playwright test — dashboard render", progress=0.56
        )
        _emit_evidence(run_id, "dashboard.png", iteration, label="dashboard renderizado")
        time.sleep(STEP_DELAY)

        if first_pass:
            _emit_evidence(
                run_id, "regression-diff.png", iteration, label="regressão visual detectada"
            )
            _emit_evidence(
                run_id, "regression-fail.png", iteration, label="pytest report (3 falhas)"
            )
            _emit_regression(run_id, iteration, passed=False, failing=FAILING_TESTS_FIRST_RUN)
            _emit_step(
                run_id, 5, "tests-regression", "failed", "✗ 3 regressões detectadas", progress=0.6
            )
            time.sleep(STEP_DELAY)
        else:
            _emit_evidence(
                run_id, "regression-pass.png", iteration, label=f"pytest report — round {iteration}"
            )
            _emit_regression(run_id, iteration, passed=True, failing=[])
            _emit_step(
                run_id,
                5,
                "tests-regression",
                "ok",
                "✓ regressão passou em todos os 47 testes",
                progress=0.62,
            )
            time.sleep(STEP_DELAY)

        # Step 6 — security
        _do_step(
            run_id, 6, "security", "secret scan + npm audit (0 high, 0 critical)", progress=0.68
        )

        if not first_pass:
            _emit_evidence(
                run_id, "coverage.png", iteration, label="coverage 92.4% — acima do gate"
            )
            break

        # Step 7 — fix loop kicks in
        _emit_step(
            run_id,
            7,
            "fix-loop",
            "running",
            f"3 testes falharam · iniciando rodada {iteration + 1} de {MAX_ITERATIONS}",
            progress=0.7,
        )
        _emit_log(run_id, "  › patch sugerido: revert primary color #22d3ee → #7c5cff")
        _emit_log(run_id, "  › patch sugerido: ajustar regex de validação de email")
        time.sleep(STEP_DELAY * 2)
        _emit_step(
            run_id,
            7,
            "fix-loop",
            "ok",
            "patches aplicados no worktree, repetindo dev → tests",
            progress=0.72,
        )

        iteration += 1

    if iteration > MAX_ITERATIONS:
        failed = True
        _emit_step(
            run_id,
            7,
            "fix-loop",
            "failed",
            f"esgotou MAX_ITERATIONS={MAX_ITERATIONS} sem passar",
            progress=0.75,
        )
        summary = (
            f"Sprint {req.sprint_id}: falhou após {MAX_ITERATIONS} rounds — testes não passaram"
        )
        _emit_done(run_id, failed=True, summary=summary, pr_url=None)
        return {"failed": True, "summary": summary, "pr_url": None, "last_step": 7}

    # Steps 8-10 — commit, PR, deliver
    _do_step(
        run_id,
        8,
        "commit",
        f"git commit -m 'feat: deliver {len(selected)} item(s)' && git push",
        progress=0.85,
    )
    pr_url = "https://github.com/example/repo/pull/4242"
    _do_step(run_id, 9, "create-pr", f"PR aberto → {pr_url}", progress=0.93)
    _do_step(
        run_id, 10, "review-and-deliver", "diff checks OK · RunReport.json salvo", progress=1.0
    )

    summary = (
        f"Sprint {req.sprint_id}: 10/10 steps OK · {len(selected)} item(s) entregues "
        f"· {iteration - 1} round(s) de fix loop · PR aberto"
    )
    _emit_done(run_id, failed=failed, summary=summary, pr_url=pr_url)
    return {"failed": failed, "summary": summary, "pr_url": pr_url, "last_step": 10}


# ---------- emit helpers ----------


def _do_step(run_id: str, step: int, name: str, msg: str, progress: float) -> None:
    _emit_step(run_id, step, name, "running", msg, progress=max(0.0, progress - 0.03))
    time.sleep(STEP_DELAY)
    _emit_step(run_id, step, name, "ok", msg, progress=progress)


def _emit_step(
    run_id: str,
    step: int,
    name: str,
    status: str,
    message: str | None,
    progress: float | None = None,
) -> None:
    payload: dict[str, Any] = {
        "type": "step",
        "step": step,
        "name": name,
        "status": status,
    }
    if message is not None:
        payload["message"] = message
    if progress is not None:
        payload["progress"] = round(progress, 3)
    events.publish_threadsafe(run_id, payload)


def _emit_log(run_id: str, message: str) -> None:
    events.publish_threadsafe(run_id, {"type": "log", "message": message})


def _emit_loop(run_id: str, iteration: int, max_iterations: int) -> None:
    events.publish_threadsafe(
        run_id,
        {
            "type": "loop",
            "iteration": iteration,
            "max_iterations": max_iterations,
            "message": f"round {iteration}/{max_iterations}",
        },
    )


def _emit_regression(run_id: str, iteration: int, passed: bool, failing: list[str]) -> None:
    events.publish_threadsafe(
        run_id,
        {
            "type": "regression",
            "iteration": iteration,
            "status": "ok" if passed else "failed",
            "failing_tests": failing,
            "message": (
                "regressão verde" if passed else f"{len(failing)} testes regressivos falharam"
            ),
        },
    )


def _emit_evidence(run_id: str, source_name: str, iteration: int, label: str) -> None:
    src = SCREENSHOTS_DIR / source_name
    dest_dir = Path("evidence") / run_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem, ext = source_name.rsplit(".", 1)
    dest_name = f"r{iteration}-{stem}.{ext}"
    dest = dest_dir / dest_name
    if src.is_file():
        with contextlib.suppress(OSError):
            shutil.copyfile(src, dest)
    else:
        # Fallback: 1×1 PNG so the file at least exists.
        with contextlib.suppress(OSError):
            dest.write_bytes(_blank_png())
    events.publish_threadsafe(
        run_id,
        {
            "type": "evidence",
            "evidence_path": str(dest),
            "evidence_label": label,
            "iteration": iteration,
            "message": label,
        },
    )


def _emit_done(run_id: str, failed: bool, summary: str, pr_url: str | None) -> None:
    events.publish_threadsafe(
        run_id,
        {
            "type": "done",
            "failed": failed,
            "summary": summary,
            "pr_url": pr_url,
        },
    )


def _blank_png() -> bytes:
    """1×1 transparent PNG so we always have valid evidence bytes if asset missing."""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c63000100000005000100050000000049454e44ae426082"
    )
