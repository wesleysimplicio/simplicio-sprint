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
from pathlib import Path

import typer
from rich.console import Console

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
from sendsprint.scope import build_scope
from sendsprint.watch import Watcher

app = typer.Typer(add_completion=False, help="Autonomous sprint-to-PR delivery.")
console = Console()
logging.basicConfig(level=logging.INFO, format="%(message)s")

SOURCES = ("jira", "azuredevops", "github")


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
    draft: bool = typer.Option(True, help="Open PRs as drafts pending your review"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Write RunReport JSON"),
) -> None:
    """Deliver a sprint: each card → simplicio task → evidence → draft PR."""
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
        draft=draft,
    )
    report = flow.run(**_read_kwargs(source, sprint, flow.scope))
    console.print(f"[bold]{report.summary}[/bold]")
    for pr in report.prs:
        console.print(f"  PR: {pr.url or pr.number} ({pr.state})")
    if output:
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"report written to {output}")
    raise typer.Exit(code=1 if report.failed else 0)


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
    interval: int = typer.Option(15, help="Minutes between cycles in loop mode"),
    once: bool = typer.Option(False, help="Run a single cycle and exit (for cron/CI triggers)"),
    max_per_cycle: int = typer.Option(1, help="Max cards delivered per cycle"),
) -> None:
    """Unattended trigger: finish cards assigned to me, scoped with --scope mine."""
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
    draft: bool,
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
    )
    scope = _build_scope(operator, scope_mode)
    return SprintFlow(operator, target, scope=scope, draft_prs=draft)


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
