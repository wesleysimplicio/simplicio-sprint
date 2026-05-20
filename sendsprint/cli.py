"""SendSprint CLI v2 - workspace-aware, scoped, 10-step orchestration."""

# ruff: noqa: B008, I001 - Typer's documented API uses Option/Argument in defaults.

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, cast

import typer
from rich.console import Console
from rich.table import Table

from sendsprint import __version__, credentials
from sendsprint import profile as profile_mod
from sendsprint.action_catalog import (
    find_action_playbook,
    list_action_playbooks,
    write_action_catalog,
)
from sendsprint.agentic_starter import (
    DEFAULT_AGENTIC_STARTER_REF,
    DEFAULT_AGENTIC_STARTER_SOURCE,
    result_to_json,
    sync_agentic_starter,
)
from sendsprint.architecture import ArchitectureMapper, build_architecture
from sendsprint.doctor import DoctorReport, run_doctor
from sendsprint.evidence import create_evidence_bundle
from sendsprint.flow import SprintFlow
from sendsprint.ingest import extract_task_candidates
from sendsprint.mcp import install_azure_devops_mcp, serve_stdio
from sendsprint.models import Sprint
from sendsprint.models.reports import RunReport
from sendsprint.models.workspace import CodeGenerationConfig, DeployWorkflowConfig
from sendsprint.operators import AzureDevopsOperator, JiraOperator
from sendsprint.operators.base import Transport
from sendsprint.policy import AutonomyPolicy, parse_autonomy_level
from sendsprint.preflight import PreflightReport, run_preflight
from sendsprint.reports import render_executive_report
from sendsprint.runtime_readiness import (
    build_cross_stack_runtime_readiness,
    format_runtime_readiness_markdown,
)
from sendsprint.runtime_baseline import run_runtime_baseline
from sendsprint.scaffolder import Scaffolder
from sendsprint.scope import build_scope
from sendsprint.templates import catalog as validation_template_catalog
from sendsprint.tech import detect_tech
from sendsprint.trackers import GitHubIssuesTracker
from sendsprint.watch import WatchCycleResult, Watcher
from sendsprint.watch_config import parse_interval_minutes
from sendsprint.workspace import load_workspace
from sendsprint.credentials import Provider as CredentialProvider
from sendsprint.yool.runtime import dispatch_yool, inspect_run, parse_payload, resume_run, snapshot
from sendsprint.yool.tuples import TupleLog, list_runs

app = typer.Typer(
    add_completion=False,
    help="SendSprint — automated sprint delivery skill (Jira / Azure DevOps).",
)
console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


sprint_app = typer.Typer(
    invoke_without_command=True,
    add_completion=False,
    help="One-shot sprint flow plus yool/tuple runtime subcommands.",
)
app.add_typer(sprint_app, name="sprint")


@app.command()
def version() -> None:
    """Print the installed SendSprint version."""
    console.print(f"sendsprint {__version__}")


@app.command(name="read-jira")
def read_jira(
    sprint_id: int = typer.Argument(..., help="Jira sprint id"),
    transport: str = typer.Option("auto", help="auto | mcp | api | playwright"),
    base_url: str | None = typer.Option(None, envvar="JIRA_BASE_URL"),
    email: str | None = typer.Option(None, envvar="JIRA_EMAIL"),
    api_token: str | None = typer.Option(None, envvar="JIRA_API_TOKEN"),
    output: Path | None = typer.Option(None, help="Write Sprint JSON to this path"),
) -> None:
    """Step 1 — read a Jira sprint and print its items."""
    operator = JiraOperator(
        base_url=base_url,
        email=email,
        api_token=api_token,
        transport=cast(Transport, transport),
    )
    sprint = operator.read_sprint(sprint_id=sprint_id)
    _render_sprint(sprint)
    if output:
        output.write_text(sprint.model_dump_json(indent=2))
        console.print(f"[green]wrote sprint to {output}[/green]")


@app.command(name="read-ado")
def read_ado(
    iteration_path: str = typer.Argument(..., help="e.g. MyTeam\\Sprint 12"),
    transport: str = typer.Option("auto", help="auto | mcp | api | playwright"),
    organization: str | None = typer.Option(None, envvar="AZURE_DEVOPS_ORG"),
    project: str | None = typer.Option(None, envvar="AZURE_DEVOPS_PROJECT"),
    pat: str | None = typer.Option(None, envvar="AZURE_DEVOPS_PAT"),
    output: Path | None = typer.Option(None),
) -> None:
    """Step 1 — read an Azure DevOps iteration."""
    operator = AzureDevopsOperator(
        organization=organization,
        project=project,
        pat=pat,
        transport=cast(Transport, transport),
    )
    sprint = operator.read_sprint(iteration_path=iteration_path)
    _render_sprint(sprint)
    if output:
        output.write_text(sprint.model_dump_json(indent=2))
        console.print(f"[green]wrote sprint to {output}[/green]")


@app.command(name="check-architecture")
def check_architecture(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False),
    build_if_missing: bool = typer.Option(
        False, "--build", help="Generate baseline docs if missing"
    ),
) -> None:
    """Step 2 — inspect (and optionally build) repo architecture docs."""
    if build_if_missing:
        fp = detect_tech(repo_path)
        result = build_architecture(repo_path, fingerprint=fp)
        console.print(f"created: {result.created_files}")
        console.print(f"skipped: {result.skipped_files}")
        console.print(f"score: {result.final_score:.2f}  mapped: {result.is_mapped}")
    else:
        report = ArchitectureMapper().inspect(repo_path)
        console.print_json(data=json.loads(report.model_dump_json()))
        if not report.is_mapped:
            console.print(f"[yellow]missing: {', '.join(report.missing)}[/yellow]")
            sys.exit(1)


@app.command(name="detect-tech")
def detect_tech_cmd(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    """Detect a repo's tech stack (fingerprint)."""
    fp = detect_tech(repo_path)
    console.print_json(data=json.loads(fp.model_dump_json()))


@app.command(name="templates")
def templates_cmd(
    output: Path | None = typer.Option(None, "-o", help="Write templates JSON"),
) -> None:
    """List shipped validation templates."""
    data = [item.model_dump() for item in validation_template_catalog()]
    if output:
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green]wrote templates to {output}[/green]")
    else:
        table = Table(show_header=True, header_style="bold")
        for col in ("Template", "Stacks", "Install", "Unit", "E2E"):
            table.add_column(col)
        for item in validation_template_catalog():
            table.add_row(
                item.name,
                ", ".join(item.stacks),
                item.install or "-",
                item.unit or "-",
                item.e2e or "-",
            )
        console.print(table)


@app.command(name="runtime-baseline")
def runtime_baseline_cmd(
    repo_path: Path = typer.Argument(Path("."), exists=True, file_okay=False),
    output: Path | None = typer.Option(None, "-o", "--output", help="Write benchmark JSON"),
    max_files: int = typer.Option(2_000, "--max-files", help="Maximum files to scan"),
) -> None:
    """Run a cross-platform Python runtime baseline before Go/Rust split work."""
    report = run_runtime_baseline(repo_path, output=output, max_files=max_files)
    table = Table(title="Runtime baseline", show_lines=False)
    for col in ("case", "ms", "ops", "metadata"):
        table.add_column(col)
    for case in report.cases:
        table.add_row(
            case.name,
            f"{case.elapsed_ms:.3f}",
            str(case.operations),
            json.dumps(case.metadata, sort_keys=True),
        )
    console.print(table)
    if report.evidence_path:
        console.print(f"[green]wrote baseline to {report.evidence_path}[/green]")


@app.command(name="runtime-readiness")
def runtime_readiness_cmd(
    repo_path: Path = typer.Argument(Path("."), exists=True, file_okay=False),
    output: Path | None = typer.Option(None, "-o", "--output", help="Write readiness Markdown"),
) -> None:
    """Check cross-stack runtime readiness for the #105 epic."""
    report = build_cross_stack_runtime_readiness(repo_path)
    rendered = format_runtime_readiness_markdown(report)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        console.print(f"[green]wrote runtime readiness to {output}[/green]")
    else:
        console.print(rendered, markup=False)
    if report.status != "ready":
        raise typer.Exit(code=1)


action_app = typer.Typer(add_completion=False, help="Manage domain action playbooks.")
app.add_typer(action_app, name="actions")


@action_app.command("list")
def action_catalog_list(
    source: Path | None = typer.Option(None, "--source", "-s", help="Custom action catalog JSON"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write playbooks JSON"),
) -> None:
    """List domain-agnostic action playbooks."""
    playbooks = list_action_playbooks(source)
    data = [item.model_dump(mode="json") for item in playbooks]
    if output:
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green]wrote action catalog to {output}[/green]")
        return
    table = Table(title="Action playbooks", show_lines=False)
    for col in ("key", "domain", "approval", "output", "title"):
        table.add_column(col, style="cyan" if col == "key" else "")
    for item in playbooks:
        table.add_row(item.key, item.domain, item.approval_policy, item.output_format, item.title)
    console.print(table)


@action_app.command("show")
def action_catalog_show(
    key: str = typer.Argument(..., help="Action key, e.g. marketing.campaign-launch"),
    source: Path | None = typer.Option(None, "--source", "-s", help="Custom action catalog JSON"),
) -> None:
    """Show one action playbook with inputs, checks, evidence, and publish policy."""
    playbook = find_action_playbook(key, source)
    if playbook is None:
        console.print(f"[red]not found[/red]: {key}")
        raise typer.Exit(code=1)
    console.print_json(data=playbook.model_dump(mode="json"))


@action_app.command("write-default")
def action_catalog_write_default(
    output: Path = typer.Argument(Path("templates/action-catalog.json")),
) -> None:
    """Write the built-in action catalog to an editable repo-local JSON file."""
    target = write_action_catalog(output)
    console.print(f"[green]wrote action catalog to {target}[/green]")


@app.command(name="doctor")
def doctor_cmd(
    repo_path: Path = typer.Option(Path("."), "--repo", "-r", exists=True, file_okay=False),
    workspace_file: Path | None = typer.Option(None, "--workspace", "-w"),
    output: Path | None = typer.Option(None, "-o", help="Write doctor JSON"),
    llm_codegen: bool = typer.Option(False, "--llm-codegen"),
    llm_provider: str | None = typer.Option(None, "--llm-provider"),
    llm_model: str | None = typer.Option(None, "--llm-model"),
    llm_max_usd: float | None = typer.Option(None, "--llm-max-usd"),
) -> None:
    """Check whether the machine/repo are ready for autonomous sprint delivery."""
    codegen = _resolve_codegen_config(
        None,
        enabled=llm_codegen,
        provider=llm_provider,
        model=llm_model,
        max_usd=llm_max_usd,
        max_tokens=None,
    )
    report = run_doctor(repo_path, workspace_file=workspace_file, code_generation=codegen)
    _render_doctor(report)
    if output:
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[green]wrote doctor report to {output}[/green]")
    if not report.ok:
        raise typer.Exit(1)


@app.command(name="sync-agentic-starter")
def sync_agentic_starter_cmd(
    repo_path: Path = typer.Argument(Path("."), exists=True, file_okay=False, help="Repo to sync"),
    source: str = typer.Option(
        DEFAULT_AGENTIC_STARTER_SOURCE,
        "--source",
        help="Local path, GitHub URL, or owner/repo for agentic-starter",
    ),
    ref: str = typer.Option(
        DEFAULT_AGENTIC_STARTER_REF,
        "--ref",
        help="'latest', a tag, branch, or commit SHA",
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite existing scaffold files"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing"),
) -> None:
    """Sync agentic-starter scaffold files into a repo."""
    result = sync_agentic_starter(
        repo_path,
        source=source,
        ref=ref,
        force=force,
        dry_run=dry_run,
    )
    console.print_json(data=result_to_json(result))


@app.command(name="install-ado-mcp")
def install_ado_mcp_cmd(
    organization: str | None = typer.Option(None, "--organization", "--org"),
    project: str | None = typer.Option(None, "--project"),
    team: str | None = typer.Option(None, "--team"),
    config_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--config",
        help="Codex config path; defaults to ~/.codex/config.toml",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Install/configure the official Azure DevOps MCP server for Codex."""
    p = profile_mod.load()
    organization = organization or p.azuredevops.organization
    project = project or p.azuredevops.project
    team = team or p.azuredevops.team

    if not organization:
        organization = typer.prompt("azure devops organization")
    if not project:
        project = typer.prompt("azure devops project")

    result = install_azure_devops_mcp(
        organization=organization,
        project=project,
        team=team,
        config_path=config_path,
        dry_run=dry_run,
    )
    console.print_json(data=result.model_dump())


@app.command(name="mcp-serve")
def mcp_serve_cmd() -> None:
    """Expose SendSprint as an MCP stdio server."""
    serve_stdio(instream=sys.stdin.buffer, outstream=sys.stdout.buffer)


@app.command(name="run")
def run_flow(
    source: str = typer.Argument(..., help="jira | azuredevops"),
    identifier: str = typer.Argument(..., help="sprint id or iteration path"),
    workspace_file: Path | None = typer.Option(
        None, "--workspace", "-w", help="workspace.yaml path"
    ),
    repo_path: Path | None = typer.Option(None, "--repo", "-r", exists=True, file_okay=False),
    transport: str = typer.Option("auto"),
    scope_mode: str = typer.Option("all", "--scope", help="all | mine"),
    task: list[str] = typer.Option(None, "--task", help="Process only this task key (repeatable)"),
    tasks: str | None = typer.Option(
        None, "--tasks", help="Comma-separated task keys (e.g. PROJ-1,PROJ-2)"
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="Comma-separated allowed statuses (default: new,active,todo,open,in progress,...)",
    ),
    output: Path | None = typer.Option(None, "-o", help="Write RunReport JSON"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Plan delivery without writing files, branches, commits, or PRs",
    ),
    plan_output: Path | None = typer.Option(
        None,
        "--plan-output",
        help="Write DeliveryPlan JSON artifact during dry-run or normal planning",
    ),
    autonomy: str | None = typer.Option(
        None,
        "--autonomy",
        help="observe | plan | execute | commit | push | pr | release | deploy-callback",
    ),
    llm_codegen: bool | None = typer.Option(
        None,
        "--llm-codegen/--no-llm-codegen",
        help="Force-enable or disable the opt-in LLM diff generation step",
    ),
    llm_provider: str | None = typer.Option(None, "--llm-provider"),
    llm_model: str | None = typer.Option(None, "--llm-model"),
    llm_max_usd: float | None = typer.Option(None, "--llm-max-usd"),
    llm_max_tokens: int | None = typer.Option(None, "--llm-max-tokens"),
    deploy: bool | None = typer.Option(
        None,
        "--deploy/--no-deploy",
        help="Force-enable or disable the opt-in deploy callback step",
    ),
    deploy_url: str | None = typer.Option(None, "--deploy-url"),
    deploy_final_status: str | None = typer.Option(None, "--deploy-final-status"),
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help="Reuse run state to avoid duplicate delivery",
    ),
    run_id: str | None = typer.Option(None, "--run-id", help="Explicit run state id"),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass receipt cache and force worker execution for this run.",
    ),
) -> None:
    """Run the full SendSprint flow."""
    ws = load_workspace(workspace_file) if workspace_file else None
    code_generation = _resolve_codegen_config(
        ws,
        enabled=llm_codegen,
        provider=llm_provider,
        model=llm_model,
        max_usd=llm_max_usd,
        max_tokens=llm_max_tokens,
    )
    deploy_config = _resolve_deploy_config(
        ws,
        enabled=deploy,
        url=deploy_url,
        final_status=deploy_final_status,
    )

    task_keys = _collect_task_keys(task, tasks)
    allowed = _parse_csv(status)

    if source == "jira":
        operator: JiraOperator | AzureDevopsOperator = JiraOperator(transport=transport)  # type: ignore[arg-type]
        user_info = operator.current_user()
        scope = build_scope(
            mode=scope_mode,
            user_email=user_info.get("emailAddress"),
            user_account_id=user_info.get("accountId"),
            allowed_statuses=allowed,
            task_keys=task_keys,
        )
    elif source == "azuredevops":
        operator = AzureDevopsOperator(transport=transport)  # type: ignore[arg-type]
        user_info = operator.current_user()
        scope = build_scope(
            mode=scope_mode,
            user_email=user_info.get("emailAddress"),
            user_descriptor=user_info.get("descriptor"),
            user_display_name=user_info.get("displayName"),
            allowed_statuses=allowed,
            task_keys=task_keys,
        )
    else:
        raise typer.BadParameter("source must be 'jira' or 'azuredevops'")

    default_autonomy = "plan" if dry_run else "deploy-callback" if deploy is True else "pr"
    autonomy_level = parse_autonomy_level(autonomy or default_autonomy)
    flow = SprintFlow(
        operator=operator,
        workspace=ws,
        scope=scope,
        code_generation=code_generation,
        deploy=deploy_config,
        autonomy_policy=AutonomyPolicy(level=autonomy_level),
    )

    sprint_id = None
    iteration_path = None
    if source == "jira":
        sprint_id = int(identifier)
    else:
        iteration_path = identifier

    result = flow.bootstrap(
        sprint_id=sprint_id,
        iteration_path=iteration_path,
        repo_path=str(repo_path) if repo_path else None,
        dry_run=dry_run,
        resume=resume,
        run_id=run_id,
        no_cache=no_cache,
    )

    _render_sprint(result.sprint)
    if result.delivery_plan:
        console.rule("Delivery Plan")
        _render_delivery_plan(result.delivery_plan)
        if plan_output:
            plan_output.write_text(result.delivery_plan.model_dump_json(indent=2), encoding="utf-8")
            console.print(f"[green]wrote delivery plan to {plan_output}[/green]")
    if result.architecture:
        console.rule("Architecture")
        console.print_json(data=json.loads(result.architecture.model_dump_json()))
    if result.run_report:
        console.rule("Run Report")
        _render_run_report(result.run_report)
    for note in result.notes:
        console.print(f"[yellow]note:[/yellow] {note}")
    if output:
        data = (
            result.run_report.model_dump_json(indent=2)
            if result.run_report
            else result.model_dump_json(indent=2)
        )
        output.write_text(data)
        console.print(f"[green]wrote report to {output}[/green]")


@app.command(name="watch")
def watch_cmd(
    workspace_file: Path = typer.Option(
        ...,
        "--workspace",
        "-w",
        exists=True,
        dir_okay=False,
        help="Workspace YAML/JSON with a watch section",
    ),
    interval: str | None = typer.Option(
        None,
        "--interval",
        help="Polling interval, for example 15, 15m or 1h",
    ),
    autonomy: str = typer.Option(
        "plan",
        "--autonomy",
        help="observe | plan | execute | commit | push | pr | release | deploy-callback",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="List eligible tasks without modifying repos or watch state",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Run one polling cycle and exit",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reprocess tasks even if watch-state says they were already handled",
    ),
    transport: str = typer.Option("auto", "--transport", help="auto | mcp | api | playwright"),
) -> None:
    """Watch Jira/Azure DevOps periodically and process eligible assigned tasks."""
    ws = load_workspace(workspace_file)
    if not ws.watch.enabled and not dry_run:
        raise typer.BadParameter("workspace watch.enabled must be true unless --dry-run is used")
    try:
        interval_minutes = parse_interval_minutes(interval, default=ws.watch.interval_minutes)
        autonomy_level = parse_autonomy_level(autonomy)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    watcher = Watcher(
        workspace=ws,
        autonomy_policy=AutonomyPolicy(level=autonomy_level),
        transport=cast(Transport, transport),
    )
    if dry_run or once:
        result = watcher.run_once(dry_run=dry_run, force=force)
        _render_watch_cycle(result)
        return

    console.print(
        f"[green]watching {ws.watch.provider} every {interval_minutes}m "
        f"with autonomy={autonomy_level}[/green]"
    )
    while True:
        result = watcher.run_once(dry_run=False, force=force)
        _render_watch_cycle(result)
        time.sleep(interval_minutes * 60)


@app.command(name="read-github")
def read_github_cmd(
    repo: str = typer.Argument(..., help="owner/repo"),
    state: str = typer.Option("open", "--state", help="open | closed | all"),
    limit: int = typer.Option(100, "--limit"),
    output: Path | None = typer.Option(None, "-o", help="Write issues JSON"),
) -> None:
    """Read GitHub Issues as a first-class tracker source."""
    if state not in {"open", "closed", "all"}:
        raise typer.BadParameter("state must be open, closed, or all")
    issues = GitHubIssuesTracker(repo).list_issues(state=cast(Any, state), limit=limit)
    data = [issue.model_dump() for issue in issues]
    if output:
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green]wrote issues to {output}[/green]")
    table = Table(show_header=True, header_style="bold")
    for col in ("#", "Title", "Labels", "Assignees", "Milestone"):
        table.add_column(col)
    for issue in issues:
        table.add_row(
            str(issue.number),
            issue.title[:80],
            ", ".join(issue.labels) or "-",
            ", ".join(issue.assignees) or "-",
            issue.milestone or "-",
        )
    console.print(table)


@app.command(name="ingest-transcript")
def ingest_transcript_cmd(
    transcript_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, "-o", help="Write extracted candidates JSON"),
    repo: str | None = typer.Option(None, "--github-repo", help="owner/repo to create issues"),
    apply: bool = typer.Option(False, "--apply", help="Create GitHub Issues from candidates"),
    autonomy: str = typer.Option("plan", "--autonomy"),
) -> None:
    """Extract reviewable task candidates from a meeting transcript."""
    existing_titles: list[str] = []
    tracker = GitHubIssuesTracker(repo) if repo else None
    if tracker:
        existing_titles = [issue.title for issue in tracker.list_issues(state="all")]
    candidates = extract_task_candidates(
        transcript_file.read_text(encoding="utf-8"),
        existing_titles=existing_titles,
    )
    data = [candidate.model_dump() for candidate in candidates]
    if output:
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green]wrote transcript tasks to {output}[/green]")
    created: list[str] = []
    if apply:
        if not tracker:
            raise typer.BadParameter("--apply requires --github-repo")
        policy = AutonomyPolicy(level=parse_autonomy_level(autonomy))
        policy.require("comment-issue")
        for candidate in candidates:
            body = _candidate_issue_body(candidate.model_dump())
            created.append(tracker.create(candidate.title, body, labels=["transcript"]))
    table = Table(show_header=True, header_style="bold")
    for col in ("Title", "Owner", "Priority", "Due", "Sensitive"):
        table.add_column(col)
    for candidate in candidates:
        table.add_row(
            candidate.title,
            candidate.owner or "-",
            candidate.priority or "-",
            candidate.due_date or "-",
            "yes" if candidate.sensitive else "no",
        )
    console.print(table)
    if created:
        console.print("[bold]Created issues:[/bold] " + ", ".join(created))


@app.command(name="bundle-evidence")
def bundle_evidence_cmd(
    report_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path("evidence-bundles"), "--output-dir"),
) -> None:
    """Package a RunReport into a portable evidence bundle."""
    report = RunReport.model_validate_json(report_file.read_text(encoding="utf-8"))
    manifest = create_evidence_bundle(report, output_dir)
    console.print(f"[green]evidence bundle:[/green] {manifest.root}")


@app.command(name="executive-report")
def executive_report_cmd(
    report_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, "-o", help="Write Markdown report"),
) -> None:
    """Render a manager-facing sprint summary from a RunReport."""
    report = RunReport.model_validate_json(report_file.read_text(encoding="utf-8"))
    markdown = render_executive_report(report)
    if output:
        output.write_text(markdown, encoding="utf-8")
        console.print(f"[green]wrote executive report to {output}[/green]")
    else:
        console.print(markdown)


@app.command(name="preflight")
def preflight_cmd(
    provider: str = typer.Argument(..., help="jira | azuredevops"),
    identifier: str | None = typer.Argument(None, help="sprint id or iteration path"),
    workspace_file: Path | None = typer.Option(
        None, "--workspace", "-w", help="workspace.yaml path"
    ),
    repo_path: Path | None = typer.Option(None, "--repo", "-r", exists=True, file_okay=False),
    transport: str = typer.Option("auto"),
    scope_mode: str = typer.Option("all", "--scope", help="all | mine"),
    task: list[str] = typer.Option(None, "--task", help="Process only this task key (repeatable)"),
    tasks: str | None = typer.Option(None, "--tasks", help="Comma-separated task keys"),
    status: str | None = typer.Option(None, "--status", help="Comma-separated allowed statuses"),
    output: Path | None = typer.Option(None, "-o", help="Write preflight JSON"),
) -> None:
    """Check credentials, transport, repos, sprint, and link safety before delivery."""
    ws = load_workspace(workspace_file) if workspace_file else None
    task_keys = _collect_task_keys(task, tasks)
    allowed = _parse_csv(status)

    if provider == "jira":
        operator: JiraOperator | AzureDevopsOperator = JiraOperator(transport=transport)  # type: ignore[arg-type]
        user_info = operator.current_user()
        scope = build_scope(
            mode=scope_mode,
            user_email=user_info.get("emailAddress"),
            user_account_id=user_info.get("accountId"),
            allowed_statuses=allowed,
            task_keys=task_keys,
        )
    elif provider == "azuredevops":
        operator = AzureDevopsOperator(transport=transport)  # type: ignore[arg-type]
        user_info = operator.current_user()
        scope = build_scope(
            mode=scope_mode,
            user_email=user_info.get("emailAddress"),
            user_descriptor=user_info.get("descriptor"),
            user_display_name=user_info.get("displayName"),
            allowed_statuses=allowed,
            task_keys=task_keys,
        )
    else:
        raise typer.BadParameter("provider must be 'jira' or 'azuredevops'")

    report = run_preflight(
        operator,
        identifier=identifier,
        workspace=ws,
        repo_path=repo_path,
        scope=scope,
    )
    _render_preflight(report)
    if output:
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[green]wrote preflight to {output}[/green]")
    if not report.ok:
        raise typer.Exit(1)


@app.command()
def init(
    repo_path: Path = typer.Argument(Path("."), help="Repo to scan and scaffold .specs/ for"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing spec files"),
    offline: bool = typer.Option(
        False, "--offline", help="Skip the LLM and write deterministic templates"
    ),
    sync_starter: bool = typer.Option(
        True,
        "--sync-agentic-starter/--no-sync-agentic-starter",
        help="Best-effort sync of the latest agentic-starter structure",
    ),
) -> None:
    """Auto-discover repo + LLM-fill .specs/{product,architecture}/*.md baselines.

    Use ``--offline`` to skip the LLM call (no API key required) and emit
    template-only files seeded with detected facts. Run ``init --force`` after
    setting your API key to overwrite with LLM-drafted versions.
    """
    from rich.status import Status

    repo = repo_path.expanduser().resolve()
    console.print(f"[bold]scaffolding[/bold] {repo}")
    scaffolder = Scaffolder(repo)
    with Status("[cyan]scanning repo...[/cyan]", console=console):
        signals = scaffolder.discover()
    langs = ", ".join(signals.primary_languages) or "unknown"
    console.print(f"  files={signals.file_count} techs={langs}")
    console.print(f"  manifests={list(signals.manifests)} docs={list(signals.docs)}")
    label = "templating" if offline else "asking LLM"
    with Status(f"[cyan]{label}: starting...[/cyan]", console=console) as status:

        def _on_step(key: str) -> None:
            status.update(f"[cyan]{label}: {key}.md[/cyan]")

        outputs = scaffolder.generate(signals, offline=offline, on_step=_on_step)
    result = scaffolder.write(outputs, force=force)
    for p in result.created:
        console.print(f"[green]created[/green] {p.relative_to(repo)}")
    for p in result.skipped:
        console.print(f"[yellow]skipped[/yellow] {p.relative_to(repo)} (exists, use --force)")
    if offline:
        console.print(
            "[yellow]note:[/yellow] templates only. set ANTHROPIC_API_KEY (or LLM_PROVIDER) "
            "and re-run with [bold]--force[/bold] for LLM-drafted specs."
        )
    if sync_starter:
        try:
            sync_result = sync_agentic_starter(repo)
        except Exception as exc:  # pragma: no cover - defensive CLI UX
            console.print(f"[yellow]agentic-starter sync skipped:[/yellow] {exc}")
        else:
            console.print(
                "[green]agentic-starter[/green] "
                f"created={len(sync_result.created)} updated={len(sync_result.updated)} "
                f"skipped={len(sync_result.skipped)} ref={sync_result.resolved_ref}"
            )


@app.command()
def login(
    provider: str = typer.Argument(..., help="jira | azuredevops"),
) -> None:
    """Prompt and persist credentials for a provider in the OS keyring."""
    if provider == "jira":
        base_url = typer.prompt("jira base url (https://your-org.atlassian.net)")
        account, _ = credentials.get_or_prompt(
            "jira",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
            account_label="email",
            secret_label="API token",
        )
        profile_mod.update(
            **{
                "default_provider": "jira",
                "jira.base_url": base_url,
                "jira.email": account,
            }
        )
        console.print(f"[green]logged in to jira as {account}[/green]")
    elif provider == "azuredevops":
        organization = typer.prompt("azure devops organization")
        project = typer.prompt("azure devops project")
        team = typer.prompt("azure devops team", default="")
        account, _ = credentials.get_or_prompt(
            "azuredevops",
            "AZURE_DEVOPS_ORG",
            "AZURE_DEVOPS_PAT",
            account_label="organization",
            secret_label="PAT",
        )
        profile_mod.update(
            **{
                "default_provider": "azuredevops",
                "azuredevops.organization": organization,
                "azuredevops.project": project,
                "azuredevops.team": team or None,
            }
        )
        install_azure_devops_mcp(
            organization=organization,
            project=project,
            team=team or None,
        )
        console.print(
            f"[green]logged in to azuredevops org={organization} project={project}[/green]"
        )
    else:
        raise typer.BadParameter("provider must be 'jira' or 'azuredevops'")


@app.command()
def logout(
    provider: str = typer.Argument(..., help="jira | azuredevops"),
    account: str | None = typer.Argument(
        None, help="account/email to forget (default: from profile)"
    ),
) -> None:
    """Remove stored credentials for a provider."""
    p = profile_mod.load()
    if not account:
        if provider == "jira":
            account = p.jira.email
        elif provider == "azuredevops":
            account = p.azuredevops.organization
    if not account:
        raise typer.BadParameter("no account known; pass it explicitly")
    credentials.delete_secret(cast(CredentialProvider, provider), account)
    console.print(f"[green]forgot {provider} credentials for {account}[/green]")


@sprint_app.callback(invoke_without_command=True)
def sprint(
    ctx: typer.Context,
    provider: str | None = typer.Option(
        None, "--provider", help="jira | azuredevops (defaults to profile)"
    ),
    identifier: str | None = typer.Option(
        None, "--id", help="sprint id or iteration path (defaults to profile)"
    ),
    repo_path: Path | None = typer.Option(None, "--repo", "-r", help="defaults to profile or cwd"),
    workspace_file: Path | None = typer.Option(None, "--workspace", "-w"),
    scope_mode: str | None = typer.Option(None, "--scope", help="all | mine"),
    task: list[str] = typer.Option(None, "--task", help="Process only this task key (repeatable)"),
    tasks: str | None = typer.Option(None, "--tasks", help="Comma-separated task keys"),
    status: str | None = typer.Option(None, "--status", help="Comma-separated allowed statuses"),
    pick: bool = typer.Option(False, "--pick", help="Interactive picker: [a]ll / [m]ine / [c]ode"),
    output: Path | None = typer.Option(None, "-o"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Plan delivery without writing files, branches, commits, or PRs",
    ),
    llm_codegen: bool | None = typer.Option(
        None,
        "--llm-codegen/--no-llm-codegen",
        help="Force-enable or disable the opt-in LLM diff generation step",
    ),
    llm_provider: str | None = typer.Option(None, "--llm-provider"),
    llm_model: str | None = typer.Option(None, "--llm-model"),
    llm_max_usd: float | None = typer.Option(None, "--llm-max-usd"),
    llm_max_tokens: int | None = typer.Option(None, "--llm-max-tokens"),
    deploy: bool | None = typer.Option(
        None,
        "--deploy/--no-deploy",
        help="Force-enable or disable the opt-in deploy callback step",
    ),
    deploy_url: str | None = typer.Option(None, "--deploy-url"),
    deploy_final_status: str | None = typer.Option(None, "--deploy-final-status"),
    resume: bool = typer.Option(
        True,
        "--resume/--no-resume",
        help="Reuse run state to avoid duplicate delivery",
    ),
    run_id: str | None = typer.Option(None, "--run-id", help="Explicit run state id"),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass receipt cache and force worker execution for this run.",
    ),
) -> None:
    """One-shot — runs the full 10-step flow with credentials and defaults from profile.

    Equivalent to: ``run <provider> <id> --scope mine``. Prompts for missing pieces once.
    """
    if ctx.invoked_subcommand is not None:
        return
    p = profile_mod.load()
    provider = provider or p.default_provider
    if not provider:
        provider = typer.prompt("provider", default="jira")

    task_keys = _collect_task_keys(task, tasks)
    allowed = _parse_csv(status)

    if pick and not task_keys and not scope_mode:
        scope_mode, task_keys = _interactive_picker()

    scope_mode = scope_mode or p.default_scope or "mine"
    repo = repo_path or (Path(p.default_repo_path) if p.default_repo_path else Path.cwd())
    ws_path = workspace_file or (Path(p.default_workspace) if p.default_workspace else None)
    ws = load_workspace(ws_path) if ws_path else None
    code_generation = _resolve_codegen_config(
        ws,
        enabled=llm_codegen,
        provider=llm_provider,
        model=llm_model,
        max_usd=llm_max_usd,
        max_tokens=llm_max_tokens,
    )
    deploy_config = _resolve_deploy_config(
        ws,
        enabled=deploy,
        url=deploy_url,
        final_status=deploy_final_status,
    )

    if provider == "jira":
        email, token = credentials.get_or_prompt(
            "jira",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
            account_label="email",
            secret_label="API token",
        )
        operator: JiraOperator | AzureDevopsOperator = JiraOperator(
            base_url=p.jira.base_url, email=email, api_token=token, transport="auto"
        )
        if not identifier:
            if p.jira.default_sprint_id:
                identifier = str(p.jira.default_sprint_id)
            else:
                identifier = typer.prompt("jira sprint id")
        user_info = operator.current_user()
        scope = build_scope(
            mode=scope_mode,
            user_email=user_info.get("emailAddress"),
            user_account_id=user_info.get("accountId"),
            allowed_statuses=allowed,
            task_keys=task_keys,
        )
        sprint_id: int | None = int(identifier)
        iteration_path: str | None = None
    elif provider == "azuredevops":
        organization, pat = credentials.get_or_prompt(
            "azuredevops",
            "AZURE_DEVOPS_ORG",
            "AZURE_DEVOPS_PAT",
            account_label="organization",
            secret_label="PAT",
        )
        operator = AzureDevopsOperator(
            organization=p.azuredevops.organization or organization,
            project=p.azuredevops.project,
            pat=pat,
            transport="auto",
        )
        if not identifier:
            if p.azuredevops.default_iteration:
                identifier = p.azuredevops.default_iteration
            else:
                identifier = typer.prompt("ado iteration path (e.g. MyTeam\\Sprint 12)")
        user_info = operator.current_user()
        scope = build_scope(
            mode=scope_mode,
            user_email=user_info.get("emailAddress"),
            user_descriptor=user_info.get("descriptor"),
            user_display_name=user_info.get("displayName"),
            allowed_statuses=allowed,
            task_keys=task_keys,
        )
        sprint_id = None
        iteration_path = identifier
    else:
        raise typer.BadParameter("provider must be 'jira' or 'azuredevops'")

    flow = SprintFlow(
        operator=operator,
        workspace=ws,
        scope=scope,
        code_generation=code_generation,
        deploy=deploy_config,
    )
    result = flow.bootstrap(
        sprint_id=sprint_id,
        iteration_path=iteration_path,
        repo_path=str(repo) if repo else None,
        dry_run=dry_run,
        resume=resume,
        run_id=run_id,
        no_cache=no_cache,
    )

    _render_sprint(result.sprint)
    if result.delivery_plan:
        console.rule("Delivery Plan")
        _render_delivery_plan(result.delivery_plan)
    if result.architecture:
        console.rule("Architecture")
        console.print_json(data=json.loads(result.architecture.model_dump_json()))
    if result.run_report:
        console.rule("Run Report")
        _render_run_report(result.run_report)
    for note in result.notes:
        console.print(f"[yellow]note:[/yellow] {note}")
    if output:
        data = (
            result.run_report.model_dump_json(indent=2)
            if result.run_report
            else result.model_dump_json(indent=2)
        )
        output.write_text(data)
        console.print(f"[green]wrote report to {output}[/green]")


@sprint_app.command("dispatch")
def sprint_dispatch_cmd(
    yool_id: str = typer.Argument(..., help="Catalog yool id, e.g. agent.codex.plan"),
    payload: str = typer.Option(..., "--payload", help="JSON payload for the tuple"),
    run_id: str | None = typer.Option(None, "--run-id", help="Optional existing run id"),
) -> None:
    """Emit one tuple into the append-only log using the shared CLI/MCP dispatch path."""
    result = dispatch_yool(yool_id, parse_payload(payload), run_id=run_id)
    console.print_json(data=result)


@sprint_app.command("snapshot")
def sprint_snapshot_cmd(
    limit: int = typer.Option(5, "--limit", min=1, help="How many recent runs to include."),
) -> None:
    """Show the yool catalog and recent tuple-run summaries."""
    console.print_json(data=snapshot(limit=limit))


@sprint_app.command("inspect")
def sprint_inspect_cmd(
    run_id: str = typer.Argument(..., help="Tuple run id"),
    cost: bool = typer.Option(False, "--cost", help="Print aggregated cost rollup"),
) -> None:
    """Inspect one tuple run: DAG/tree, receipts, and optional cost rollup."""
    data = inspect_run(run_id)
    if data["tree"]:
        console.print(data["tree"])
    console.print_json(data={"run_id": data["run_id"], "tuples": data["tuples"]})
    if cost:
        console.print_json(data=data["cost"])


@sprint_app.command("resume")
def sprint_resume_cmd(
    run_or_tuple_id: str = typer.Argument(
        ...,
        help="Tuple run id or tuple id to replay pending work from",
    ),
) -> None:
    """Replay pending tuples from the append-only tuple log."""
    console.print_json(data=resume_run(_resolve_run_id(run_or_tuple_id)))


def _resolve_run_id(identifier: str) -> str:
    if identifier.startswith("run-") or identifier.startswith("tuple-"):
        return identifier
    if identifier.startswith("sha256:"):
        for run_id in list_runs():
            log = TupleLog(run_id)
            if any(tup.id == identifier for tup in log.tuples()):
                return run_id
    raise typer.BadParameter("identifier must be a tuple run id or an existing tuple id")


def _render_sprint(sprint: Sprint) -> None:
    console.rule(f"Sprint {sprint.id}: {sprint.name} ({sprint.transport})")
    table = Table(show_header=True, header_style="bold")
    for col in ("Key", "Type", "Title", "Status", "Assignee", "SP"):
        table.add_column(col)
    for item in sprint.items:
        table.add_row(
            item.key,
            item.type,
            (item.title or "")[:60],
            item.status,
            item.assignee or "-",
            str(item.story_points) if item.story_points is not None else "-",
        )
    console.print(table)
    console.print(
        f"[bold]totals[/bold] stories={len(sprint.stories)} tasks={len(sprint.tasks)} "
        f"subtasks={len(sprint.subtasks)} bugs={len(sprint.bugs)} "
        f"epics={len(sprint.epics)} features={len(sprint.features)} issues={len(sprint.issues)}"
    )


def _render_run_report(report) -> None:
    table = Table(show_header=True, header_style="bold")
    for col in ("Step", "Name", "Status", "Message"):
        table.add_column(col)
    for s in report.steps:
        style = {"ok": "green", "failed": "red", "skipped": "yellow"}.get(s.status, "")
        table.add_row(str(s.step), s.name, f"[{style}]{s.status}[/{style}]", (s.message or "")[:80])
    console.print(table)
    if report.prs:
        console.print(f"[bold]PRs:[/bold] {', '.join(p.url or str(p.number) for p in report.prs)}")
    console.print(f"[bold]Summary:[/bold] {report.summary}")


def _render_delivery_plan(plan) -> None:
    table = Table(show_header=True, header_style="bold")
    for col in ("Item", "Repo", "Branch", "Target", "Confidence", "Reason"):
        table.add_column(col)
    for delivery in plan.deliveries:
        style = {"high": "green", "medium": "yellow", "low": "red"}.get(delivery.confidence, "")
        table.add_row(
            delivery.item_key,
            Path(delivery.repo).name,
            delivery.branch,
            delivery.target_branch,
            f"[{style}]{delivery.confidence}[/{style}]",
            delivery.reason[:60],
        )
    console.print(table)
    if plan.warnings:
        for warning in plan.warnings:
            console.print(f"[yellow]warning:[/yellow] {warning}")
    console.print(f"[bold]Plan:[/bold] {plan.summary()}")


def _render_watch_cycle(result: WatchCycleResult) -> None:
    console.rule(f"Watch {result.provider} sprint={result.sprint_id}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Action")
    table.add_column("Task")
    table.add_column("State")
    table.add_column("Revision")
    table.add_column("Run")
    table.add_column("Branch", overflow="fold", no_wrap=True)
    table.add_column("Reason/PR", overflow="fold")
    rows = [*result.eligible, *result.processed, *result.skipped, *result.blocked]
    for decision in rows:
        table.add_row(
            decision.action,
            decision.key or decision.task_id,
            decision.status,
            decision.revision or "-",
            decision.run_id or "-",
            decision.branch or "-",
            decision.pr_url or decision.reason or "-",
        )
    console.print(table)
    console.print(f"[bold]Watch:[/bold] {result.summary()}")


def _render_preflight(report: PreflightReport) -> None:
    console.rule(f"Preflight {report.provider}")
    table = Table(show_header=True, header_style="bold")
    for col in ("Check", "Status", "Message"):
        table.add_column(col)
    for check in report.checks:
        style = {"ok": "green", "warn": "yellow", "failed": "red"}[check.status]
        table.add_row(check.name, f"[{style}]{check.status}[/{style}]", check.message[:100])
    console.print(table)
    console.print(f"[bold]Result:[/bold] {'ok' if report.ok else 'failed'}")


def _render_doctor(report: DoctorReport) -> None:
    console.rule("SendSprint Doctor")
    table = Table(show_header=True, header_style="bold")
    for col in ("Check", "Status", "Message", "Remediation"):
        table.add_column(col)
    for check in report.checks:
        style = {"ok": "green", "warn": "yellow", "failed": "red"}[check.status]
        table.add_row(
            check.name,
            f"[{style}]{check.status}[/{style}]",
            check.message[:90],
            check.remediation or "-",
        )
    console.print(table)
    if report.template:
        console.print(
            f"[bold]Template:[/bold] {report.template.name} "
            f"({', '.join(report.template.commands()[:4])})"
        )
    console.print(f"[bold]Result:[/bold] {'ok' if report.ok else 'failed'}")


def _candidate_issue_body(candidate: dict[str, Any]) -> str:
    refs = candidate.get("source_refs") or []
    ref_lines = "\n".join(
        f"- Lines {ref.get('line_start')}-{ref.get('line_end')}: {ref.get('excerpt')}"
        for ref in refs
    )
    ac = "\n".join(f"- [ ] {item}" for item in candidate.get("acceptance_criteria") or [])
    return f"""## Transcript Task

{candidate.get("summary") or candidate.get("title")}

## Metadata

- Owner: {candidate.get("owner") or "n/a"}
- Priority: {candidate.get("priority") or "n/a"}
- Due date: {candidate.get("due_date") or "n/a"}
- Sensitive content flagged: {candidate.get("sensitive")}

## Acceptance Criteria

{ac or "- [ ] Review and refine acceptance criteria"}

## Source Traceability

{ref_lines or "- No source refs"}
"""


def _resolve_codegen_config(
    workspace: object | None,
    *,
    enabled: bool | None = None,
    provider: str | None = None,
    model: str | None = None,
    max_usd: float | None = None,
    max_tokens: int | None = None,
) -> CodeGenerationConfig:
    base = (
        workspace.code_generation
        if workspace is not None and hasattr(workspace, "code_generation")
        else CodeGenerationConfig()
    )
    updates: dict[str, Any] = {}
    if enabled is not None:
        updates["enabled"] = enabled
    if provider is not None:
        updates["provider"] = provider
    if model is not None:
        updates["model"] = model
    if max_usd is not None:
        updates["max_usd"] = max_usd
    if max_tokens is not None:
        updates["max_tokens"] = max_tokens
    return base.model_copy(update=updates)


def _resolve_deploy_config(
    workspace: object | None,
    *,
    enabled: bool | None = None,
    url: str | None = None,
    final_status: str | None = None,
) -> DeployWorkflowConfig:
    base = (
        workspace.deploy
        if workspace is not None and hasattr(workspace, "deploy")
        else DeployWorkflowConfig()
    )
    updates: dict[str, Any] = {}
    if enabled is not None:
        updates["enabled"] = enabled
    if url is not None:
        updates["url"] = url
    if final_status is not None:
        updates["final_status"] = final_status
    return base.model_copy(update=updates)


def _parse_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    parts = [v.strip() for v in value.split(",") if v.strip()]
    return parts or None


def _collect_task_keys(repeatable: list[str] | None, csv: str | None) -> list[str] | None:
    keys: list[str] = []
    if repeatable:
        keys.extend(k.strip() for k in repeatable if k and k.strip())
    if csv:
        keys.extend(k.strip() for k in csv.split(",") if k.strip())
    return keys or None


def _interactive_picker() -> tuple[str, list[str] | None]:
    """Prompt user: [a]ll / [m]ine / [c]ode. Returns (scope_mode, task_keys)."""
    choice = typer.prompt("scope? [a]ll / [m]ine / [c]ode", default="m").strip().lower()
    if choice.startswith("a"):
        return "all", None
    if choice.startswith("c"):
        raw = typer.prompt("task code(s), comma-separated (e.g. PROJ-1,PROJ-2)")
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        return "all", keys or None
    return "mine", None


catalog_app = typer.Typer(
    add_completion=False,
    help="Manage the HAMT-backed agent capability catalog (yool/tuple/HAMT).",
)
app.add_typer(catalog_app, name="catalog")
sprint_app.add_typer(catalog_app, name="catalog")

_DEFAULT_AGENT_CATALOG = Path(".catalog/agents.json")
_CATALOG_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_agent_catalog.py"


def _build_catalog_file(output: Path, *, check: bool = False) -> None:
    cmd = [sys.executable, str(_CATALOG_SCRIPT), "--output", str(output)]
    if check:
        cmd.append("--check")
    result = __import__("subprocess").run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip() or "catalog build failed"
        raise typer.BadParameter(message)
    if result.stdout.strip():
        console.print(result.stdout.strip())


def _load_spec_catalog(path: Path) -> dict[str, Any]:
    from sendsprint.yool.catalog_v2 import load_catalog

    if not path.exists():
        _build_catalog_file(path)
    return load_catalog(path)


def _render_spec_entries(entries: list[Any]) -> None:
    from sendsprint.yool.catalog_v2 import to_table_rows

    table = Table(title="Agent yools", show_lines=False)
    for column in ("yool_id", "authority", "lane", "cpu%", "disk_mb", "timeout_s", "description"):
        table.add_column(column, style="cyan" if column == "yool_id" else "")
    for row in to_table_rows(entries):
        table.add_row(
            row["yool_id"],
            row["authority"],
            row["lane"],
            row["cpu%"],
            row["disk_mb"],
            row["timeout_s"],
            row["description"],
        )
    console.print(table)


@catalog_app.command("build")
def catalog_build(
    output: Path = typer.Option(
        _DEFAULT_AGENT_CATALOG,
        "--output",
        "-o",
        help="Destination JSON path (default .catalog/agents.json).",
    ),
    check: bool = typer.Option(False, "--check", help="Fail if the committed catalog drifted."),
) -> None:
    """Build or validate the spec-shaped `.catalog/agents.json` file."""
    _build_catalog_file(output, check=check)


@catalog_app.command("list")
def catalog_list(
    source: Path = typer.Option(
        _DEFAULT_AGENT_CATALOG,
        "--source",
        "-s",
        help="Catalog JSON path; built from registry if missing.",
    ),
) -> None:
    """List every yool in the spec-shaped catalog."""
    from sendsprint.yool.catalog_v2 import list_yools

    _render_spec_entries(list_yools(_load_spec_catalog(source)))


@catalog_app.command("find")
def catalog_find(
    query: str = typer.Argument(
        ..., help="Regex, glob, or substring pattern to match against yool_id."
    ),
    source: Path = typer.Option(
        _DEFAULT_AGENT_CATALOG,
        "--source",
        "-s",
        help="Catalog JSON path; built from registry if missing.",
    ),
) -> None:
    """Find yools via regex (/expr/), glob (*foo*), or substring."""
    import fnmatch
    import re

    from sendsprint.yool.catalog_v2 import list_yools

    entries = list_yools(_load_spec_catalog(source))
    if query.startswith("/") and query.endswith("/") and len(query) > 2:
        regex = re.compile(query[1:-1], re.IGNORECASE)
        hits = [entry for entry in entries if regex.search(entry.yool_id)]
    elif any(ch in query for ch in "*?[]"):
        pattern = query.lower()
        hits = [entry for entry in entries if fnmatch.fnmatch(entry.yool_id.lower(), pattern)]
    else:
        lowered = query.lower()
        hits = [entry for entry in entries if lowered in entry.yool_id.lower()]
    if not hits:
        console.print(f"[yellow]no yools match[/yellow] '{query}'")
        raise typer.Exit(code=1)
    _render_spec_entries(hits)


@catalog_app.command("show")
def catalog_show(
    yool_id: str = typer.Argument(..., help="Exact yool id, e.g. agent.codex.plan"),
    source: Path = typer.Option(
        _DEFAULT_AGENT_CATALOG,
        "--source",
        "-s",
        help="Catalog JSON path; built from registry if missing.",
    ),
) -> None:
    """Show the full record for one yool, including its HAMT slot path."""
    from sendsprint.yool.catalog_v2 import lookup_yool

    catalog = _load_spec_catalog(source)
    entry = lookup_yool(catalog, yool_id)
    if entry is None:
        console.print(f"[red]not found[/red]: {yool_id}")
        raise typer.Exit(code=1)
    console.print_json(
        data={
            "yool_id": entry.yool_id,
            "hash": entry.hash_bits,
            "slots": list(entry.slots),
            "tuple": entry.tuple,
        }
    )


@app.command(name="web")
def web_cmd(
    port: int = typer.Option(5173, "--port", "-p", help="Port for the web control plane"),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Start the localhost web control plane (API + UI)."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is required: pip install uvicorn[/red]")
        raise typer.Exit(1) from None

    console.print(f"[green]SendSprint web control plane v{__version__}[/green]")
    console.print(f"  listening on http://{host}:{port}")
    console.print(f"  docs at http://{host}:{port}/docs")
    uvicorn.run(
        "sendsprint.api.server:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
