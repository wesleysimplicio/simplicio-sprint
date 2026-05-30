"""SendSprint CLI — read a sprint, let simplicio-cli execute, ship draft PRs.

SendSprint is the agent that owns the flow; simplicio-cli is the executor it
calls per task. Commands:

    sendsprint version
    sendsprint login   jira|azuredevops|github
    sendsprint logout  jira|azuredevops|github
    sendsprint run     <source> <sprint> --repo PATH --scope mine
    sendsprint watch   <source> <sprint> --repo PATH --once   # unattended trigger
"""

# ruff: noqa: B008 - Typer's documented API uses Option/Argument call in defaults.

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from sendsprint import __version__
from sendsprint import credentials as creds
from sendsprint.flow import RepoTarget, SprintFlow
from sendsprint.models import ScopeConfig
from sendsprint.operators import (
    AzureDevopsOperator,
    BaseOperator,
    GitHubIssuesOperator,
    JiraOperator,
)
from sendsprint.progress import ProgressEvent
from sendsprint.prompt import PromptFanout
from sendsprint.scope import build_scope
from sendsprint.watch import Watcher

app = typer.Typer(add_completion=False, help="Autonomous sprint-to-PR delivery.")
console = Console()
logger = logging.getLogger("sendsprint.cli")

SOURCES = ("jira", "azuredevops", "github")


@app.callback()
def _main(
    log_level: str = typer.Option("INFO", "--log-level", help="DEBUG | INFO | WARNING | ERROR"),
    log_file: Path | None = typer.Option(None, "--log-file", help="Override the log file path"),
    log_json: bool = typer.Option(False, "--log-json", help="Write logs as JSON lines"),
) -> None:
    """Configure logging for every command (logs capture every step to a file)."""
    from sendsprint.logging_setup import configure

    path = configure(level=log_level, log_file=log_file, json_lines=log_json)
    logger.debug("sendsprint %s — logging to %s", __version__, path)


@app.command()
def version() -> None:
    """Print the SendSprint version."""
    console.print(f"SendSprint {__version__}")


@app.command()
def login(provider: str) -> None:
    """Store credentials for a source in the OS keyring (one-time)."""
    provider = provider.lower()
    if provider == "jira":
        creds.get_or_prompt("jira", "JIRA_EMAIL", "JIRA_API_TOKEN", account_label="email")
    elif provider == "azuredevops":
        creds.get_or_prompt(
            "azuredevops", "AZURE_DEVOPS_ORG", "AZURE_DEVOPS_PAT", account_label="organization"
        )
    elif provider == "github":
        typer.echo("github uses the GITHUB_TOKEN environment variable; no keyring entry needed.")
    else:
        raise typer.BadParameter(f"provider must be one of {SOURCES}")


@app.command()
def logout(provider: str, account: str) -> None:
    """Delete a stored credential."""
    creds.delete_secret(provider, account)  # type: ignore[arg-type]
    console.print(f"removed {provider} credential for {account}")


@app.command()
def update(
    cli: bool = typer.Option(True, help="Upgrade simplicio-cli via pip"),
    prompt: bool = typer.Option(True, help="Sync the simplicio-prompt kernel via git"),
    mapper: bool = typer.Option(True, help="Sync simplicio-mapper via git"),
) -> None:
    """Pull the latest of simplicio-cli / simplicio-prompt / simplicio-mapper."""
    from sendsprint.bootstrap import Updater

    report = Updater().update_all(cli=cli, prompt=prompt, mapper=mapper)
    for result in report.results:
        console.print(f"  {result.line()}")
    raise typer.Exit(code=0 if report.ok else 1)


@app.command()
def install(
    target: list[str] = typer.Option(
        [], "--target", "-t", help="Agent(s) to install for; repeatable"
    ),
    all_: bool = typer.Option(False, "--all", help="Install for every supported agent"),
    repo: Path = typer.Option(Path("."), help="Target project directory"),
) -> None:
    """Install the SendSprint skill into each agent's convention (Cursor, Claude, ...)."""
    from sendsprint.installer import TARGETS
    from sendsprint.installer import install as do_install

    names = sorted(TARGETS) if all_ or not target else target
    try:
        results = do_install(repo, names)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    for result in results:
        console.print(f"  {result.line()}")


@app.command()
def run(
    source: str = typer.Argument(..., help="jira | azuredevops | github"),
    sprint: str = typer.Argument(..., help="Jira sprint id, ADO iteration path, or GH milestone"),
    repo: Path = typer.Option(Path("."), help="Path to the target git repo"),
    scope: str = typer.Option("mine", help="mine | all"),
    pr_provider: str = typer.Option("github", help="github | azuredevops"),
    repo_slug: str = typer.Option("", help="owner/repo (github) or repository id (ado)"),
    base: str = typer.Option("develop", help="PR target branch"),
    tech: str | None = typer.Option(None, help="Override detected stack for simplicio --stack"),
    test_command: str | None = typer.Option(None, help="Command to run for test evidence"),
    frontend_url: str | None = typer.Option(None, help="URL to screenshot for screen evidence"),
    evidence_video: bool = typer.Option(
        False,
        "--evidence-video",
        help="Render delivery-<KEY>.mp4 with hyperframes after screenshot evidence",
    ),
    draft: bool = typer.Option(True, help="Open PRs as drafts pending your review"),
    specs: bool = typer.Option(True, help="Write simplicio-mapper .specs/ task files per card"),
    fanout: bool = typer.Option(False, help="Run a simplicio-prompt subagent fan-out per card"),
    fanout_subagents: int = typer.Option(600, help="Subagents per fan-out"),
    fanout_provider: str = typer.Option("deepseek", help="simplicio-prompt provider"),
    fanout_dry_run: bool = typer.Option(False, help="Run the fan-out offline (no key/network)"),
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Run sprint plan validation before processing items",
    ),
    validate_only: bool = typer.Option(False, help="Validate the sprint plan and exit"),
    bootstrap_mapper: bool = typer.Option(
        True,
        "--bootstrap-mapper/--no-bootstrap-mapper",
        help="Create mapper context when .simplicio/project-map.json is absent",
    ),
    retro: bool = typer.Option(
        True,
        "--retro/--no-retro",
        help="Write .specs sprint RETROSPECTIVE.md after a run",
    ),
    resume: bool = typer.Option(
        False,
        "--resume",
        help="Resume pending items from .sendsprint/state/<sprint>.json",
    ),
    quiet: bool = typer.Option(False, "--quiet", help="Suppress human progress output"),
    no_update: bool = typer.Option(False, help="Skip the start-up tool update (profile-driven)"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Write RunReport JSON"),
) -> None:
    """Deliver a sprint: each card → simplicio task → evidence → draft PR."""
    _startup(no_update or quiet)
    operator = _build_operator(source)
    flow = _build_flow(
        operator,
        source=source,
        repo=repo,
        scope_mode=scope,
        pr_provider=pr_provider,
        repo_slug=repo_slug,
        base=base,
        tech=tech,
        test_command=test_command,
        frontend_url=frontend_url,
        evidence_video=evidence_video,
        draft=draft,
        write_specs=specs,
        fanout=fanout,
        fanout_subagents=fanout_subagents,
        fanout_provider=fanout_provider,
        fanout_dry_run=fanout_dry_run,
    )
    progress = None if quiet else _RunProgressRenderer(console)
    report = flow.run(
        validate_plan=validate,
        validate_only=validate_only,
        bootstrap_mapper=bootstrap_mapper,
        retro=retro,
        resume=resume,
        progress=progress,
        **_read_kwargs(source, sprint, flow.scope),
    )
    if not quiet:
        console.print(f"[bold]{report.summary}[/bold]")
        for note in report.notes:
            console.print(f"  note: {note}")
        for pr in report.prs:
            console.print(f"  PR: {pr.url or pr.number} ({pr.state})")
    _archive_report(report, quiet=quiet)
    if output:
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        if not quiet:
            console.print(f"report written to {output}")
    raise typer.Exit(code=130 if report.cancelled else 1 if report.failed else 0)


@app.command()
def watch(
    source: str = typer.Argument(..., help="jira | azuredevops | github"),
    sprint: str = typer.Argument(..., help="Jira sprint id, ADO iteration path, or GH milestone"),
    repo: Path = typer.Option(Path("."), help="Path to the target git repo"),
    pr_provider: str = typer.Option("github", help="github | azuredevops"),
    repo_slug: str = typer.Option("", help="owner/repo (github) or repository id (ado)"),
    base: str = typer.Option("develop", help="PR target branch"),
    tech: str | None = typer.Option(None, help="Override detected stack"),
    test_command: str | None = typer.Option(None, help="Command to run for test evidence"),
    evidence_video: bool = typer.Option(
        False,
        "--evidence-video",
        help="Render delivery-<KEY>.mp4 with hyperframes after screenshot evidence",
    ),
    interval: int = typer.Option(15, help="Minutes between cycles in loop mode"),
    once: bool = typer.Option(False, help="Run a single cycle and exit (for cron/CI triggers)"),
    max_per_cycle: int = typer.Option(1, help="Max cards delivered per cycle"),
    no_update: bool = typer.Option(False, help="Skip the start-up tool update (profile-driven)"),
) -> None:
    """Unattended trigger: finish cards assigned to me, scoped with --scope mine."""
    _startup(no_update)
    operator = _build_operator(source)
    flow = _build_flow(
        operator,
        source=source,
        repo=repo,
        scope_mode="mine",
        pr_provider=pr_provider,
        repo_slug=repo_slug,
        base=base,
        tech=tech,
        test_command=test_command,
        frontend_url=None,
        evidence_video=evidence_video,
        draft=True,
    )
    watcher = Watcher(flow, interval_minutes=interval, max_per_cycle=max_per_cycle)
    read_kwargs = _read_kwargs(source, sprint, flow.scope)
    if once:
        report = watcher.run_once(**read_kwargs)
        console.print(f"[bold]{report.summary}[/bold]")
        raise typer.Exit(code=1 if report.failed else 0)
    console.print(f"watching {source} {sprint} every {interval}m (scope=mine). Ctrl-C to stop.")
    watcher.loop(**read_kwargs)


# -- builders ---------------------------------------------------------------


def _startup(skip: bool) -> None:
    """Run the profile-driven tool update before a delivery. Never fatal."""
    if skip or os.getenv("SENDSPRINT_NO_UPDATE") == "1":
        return
    try:
        from sendsprint import profile as profile_mod
        from sendsprint.bootstrap import Updater

        report = Updater().run_startup(profile_mod.load())
        for result in report.results:
            console.print(f"  [dim]{result.line()}[/dim]")
    except Exception as exc:  # noqa: BLE001 — startup updates are best-effort
        logger.warning("startup update skipped: %s", exc)


def _archive_report(report: object, *, quiet: bool = False) -> None:
    """Persist the run report JSON next to the logs. Best-effort."""
    try:
        from datetime import UTC, datetime

        from sendsprint.logging_setup import log_dir

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = log_dir() / f"run-{stamp}.report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")  # type: ignore[attr-defined]
        if not quiet:
            console.print(f"[dim]run report archived to {path}[/dim]")
    except Exception as exc:  # noqa: BLE001 — archiving is best-effort
        logger.warning("could not archive run report: %s", exc)


class _RunProgressRenderer:
    def __init__(self, target_console: Console) -> None:
        self.console = target_console
        self.live: Live | None = None
        self.title = "SendSprint"
        self.total_items = 0
        self.rows: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.summary = ""

    def __call__(self, event: ProgressEvent) -> None:
        if event.kind == "run_started":
            self.title = f"SendSprint - {event.sprint_slug or event.sprint_name or 'run'}"
            self.total_items = event.total_items
            for item in event.items:
                self._ensure_row(item.key, item.type)
            self._start()
        elif event.item_key:
            self._ensure_row(event.item_key, event.item_type or "")
            row = self.rows[event.item_key]
            if event.kind == "item_started":
                row.update(status="running", message="")
            elif event.kind == "item_skipped":
                row.update(
                    status="skipped",
                    pr=event.pr_number,
                    dod=event.dod,
                    message=event.reason or "",
                )
            elif event.kind == "item_finished":
                row.update(
                    status=event.status or "done",
                    pr=event.pr_number or event.pr_url,
                    dod=event.dod,
                    elapsed_s=event.elapsed_s,
                    cost_usd=event.cost_usd,
                    message=event.message or "",
                )
        elif event.kind == "drain_requested":
            self.summary = event.message or "drain requested"
        elif event.kind == "run_finished":
            self.summary = self._summary_text(event)
        self._refresh(final=event.kind == "run_finished")

    def _ensure_row(self, key: str, item_type: str) -> None:
        if key in self.rows:
            if item_type:
                self.rows[key]["type"] = item_type
            return
        self.order.append(key)
        self.rows[key] = {
            "type": item_type,
            "status": "pending",
            "pr": None,
            "dod": None,
            "elapsed_s": None,
            "message": "",
        }

    def _start(self) -> None:
        if self.live is None:
            self.live = Live(
                self._table(),
                console=self.console,
                refresh_per_second=4,
                transient=False,
            )
            self.live.start()

    def _refresh(self, *, final: bool = False) -> None:
        if self.live is not None:
            self.live.update(self._table())
            if final:
                self.live.stop()
                self.live = None

    def _table(self) -> Table:
        table = Table(title=f"{self.title} ({self.total_items} items)")
        table.add_column("KEY")
        table.add_column("TYPE")
        table.add_column("STATUS")
        table.add_column("PR")
        table.add_column("DoD")
        table.add_column("TIME", justify="right")
        table.add_column("DETAIL")
        for key in self.order:
            row = self.rows[key]
            table.add_row(
                key,
                str(row.get("type") or "-"),
                str(row.get("status") or "pending"),
                _format_pr(row.get("pr")),
                _format_dod(row.get("dod")),
                _format_elapsed(row.get("elapsed_s")),
                str(row.get("message") or ""),
            )
        if self.summary:
            table.caption = self.summary
        return table

    def _summary_text(self, event: ProgressEvent) -> str:
        counts = _row_counts(self.rows)
        cost = event.cost_usd if event.cost_usd is not None else _row_cost(self.rows)
        parts = [
            f"totals: {counts['ok']} ok",
            f"{counts['failed']} failed",
            f"{counts['skipped']} skipped",
        ]
        if cost:
            parts.append(f"cost ~${cost:.2f}")
        if event.cancelled:
            parts.append("cancelled")
        return " | ".join(parts)


def _format_pr(value: object) -> str:
    if isinstance(value, int):
        return f"#{value}"
    if isinstance(value, str) and value:
        return value
    return "-"


def _format_dod(value: object) -> str:
    if value is True:
        return "✓"
    if value is False:
        return "✗"
    return "-"


def _format_elapsed(value: object) -> str:
    if not isinstance(value, int | float):
        return "-"
    seconds = max(0, int(round(value)))
    minutes, remaining = divmod(seconds, 60)
    return f"{minutes}m{remaining:02d}s" if minutes else f"{remaining}s"


def _row_counts(rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"ok": 0, "failed": 0, "skipped": 0}
    for row in rows.values():
        status = row.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def _row_cost(rows: dict[str, dict[str, Any]]) -> float:
    total = 0.0
    for row in rows.values():
        value = row.get("cost_usd")
        if isinstance(value, int | float):
            total += float(value)
    return total


def _build_operator(source: str) -> BaseOperator:
    source = source.lower()
    if source == "jira":
        return JiraOperator()
    if source == "azuredevops":
        return AzureDevopsOperator()
    if source == "github":
        return GitHubIssuesOperator()
    raise typer.BadParameter(f"source must be one of {SOURCES}")


def _build_flow(
    operator: BaseOperator,
    *,
    source: str,
    repo: Path,
    scope_mode: str,
    pr_provider: str,
    repo_slug: str,
    base: str,
    tech: str | None,
    test_command: str | None,
    frontend_url: str | None,
    evidence_video: bool = False,
    draft: bool,
    write_specs: bool = True,
    fanout: bool = False,
    fanout_subagents: int = 600,
    fanout_provider: str = "deepseek",
    fanout_dry_run: bool = False,
) -> SprintFlow:
    target = RepoTarget(
        path=repo,
        name=repo_slug or repo.name,
        tech=tech,
        test_command=test_command,
        base_branch=base,
        pr_provider=pr_provider,
        repo_slug=repo_slug,
        frontend_url=frontend_url,
        evidence_video=evidence_video,
    )
    scope = _build_scope(operator, scope_mode)
    fan = (
        PromptFanout(provider=fanout_provider, subagents=fanout_subagents, dry_run=fanout_dry_run)
        if fanout
        else None
    )
    return SprintFlow(
        operator, target, scope=scope, draft_prs=draft, write_specs=write_specs, fanout=fan
    )


def _build_scope(operator: BaseOperator, mode: str) -> ScopeConfig:
    if mode != "mine":
        return build_scope(mode="all")
    user = operator.current_user() if hasattr(operator, "current_user") else {}
    return build_scope(
        mode="mine",
        user_email=user.get("emailAddress") or user.get("email"),
        user_account_id=user.get("accountId"),
        user_descriptor=user.get("descriptor"),
        user_display_name=user.get("displayName") or user.get("name") or user.get("login"),
    )


def _read_kwargs(source: str, sprint: str, scope: ScopeConfig | None) -> dict[str, object]:
    source = source.lower()
    if source == "jira":
        return {"sprint_id": sprint}
    if source == "azuredevops":
        return {"iteration_path": sprint}
    # github: milestone + assignee login when scoping to me
    kwargs: dict[str, object] = {"sprint_id": sprint}
    if scope and scope.mode == "mine" and scope.user_display_name:
        kwargs["assignee"] = scope.user_display_name
    return kwargs


def main() -> None:
    app()


if __name__ == "__main__":
    main()
