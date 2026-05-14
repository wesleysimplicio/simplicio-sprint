"""SendSprint CLI v2 — workspace-aware, scoped, 9-step orchestration."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from sendsprint import __version__, credentials
from sendsprint import profile as profile_mod
from sendsprint.agentic_starter import (
    DEFAULT_AGENTIC_STARTER_REF,
    DEFAULT_AGENTIC_STARTER_SOURCE,
    result_to_json,
    sync_agentic_starter,
)
from sendsprint.architecture import ArchitectureMapper, build_architecture
from sendsprint.flow import SprintFlow
from sendsprint.models import Sprint
from sendsprint.operators import AzureDevopsOperator, JiraOperator
from sendsprint.scaffolder import Scaffolder
from sendsprint.scope import build_scope
from sendsprint.tech import detect_tech
from sendsprint.workspace import load_workspace

app = typer.Typer(
    add_completion=False,
    help="SendSprint — automated sprint delivery skill (Jira / Azure DevOps).",
)
console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


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
        base_url=base_url, email=email, api_token=api_token, transport=transport
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
        organization=organization, project=project, pat=pat, transport=transport
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
) -> None:
    """Run the full 10-step SendSprint flow."""
    ws = load_workspace(workspace_file) if workspace_file else None

    task_keys = _collect_task_keys(task, tasks)
    allowed = _parse_csv(status)

    if source == "jira":
        operator = JiraOperator(transport=transport)
        user_info = operator.current_user()
        scope = build_scope(
            mode=scope_mode,
            user_email=user_info.get("emailAddress"),
            user_account_id=user_info.get("accountId"),
            allowed_statuses=allowed,
            task_keys=task_keys,
        )
    elif source == "azuredevops":
        operator = AzureDevopsOperator(transport=transport)
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

    flow = SprintFlow(operator=operator, workspace=ws, scope=scope)

    sprint_id = None
    iteration_path = None
    if source == "jira":
        sprint_id = int(identifier)
    else:
        iteration_path = identifier

    result = flow.run(
        sprint_id=sprint_id,
        iteration_path=iteration_path,
        repo_path=str(repo_path) if repo_path else None,
    )

    _render_sprint(result.sprint)
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
            }
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
    credentials.delete_secret(provider, account)
    console.print(f"[green]forgot {provider} credentials for {account}[/green]")


@app.command()
def sprint(
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
) -> None:
    """One-shot — runs the full 10-step flow with credentials and defaults from profile.

    Equivalent to: ``run <provider> <id> --scope mine``. Prompts for missing pieces once.
    """
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

    if provider == "jira":
        email, token = credentials.get_or_prompt(
            "jira",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
            account_label="email",
            secret_label="API token",
        )
        operator = JiraOperator(
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

    flow = SprintFlow(operator=operator, workspace=ws, scope=scope)
    result = flow.run(
        sprint_id=sprint_id,
        iteration_path=iteration_path,
        repo_path=str(repo) if repo else None,
    )

    _render_sprint(result.sprint)
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


if __name__ == "__main__":
    app()
