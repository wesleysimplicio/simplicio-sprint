"""Helpers for Azure DevOps sprint URLs used by the web control plane."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse


@dataclass(frozen=True, slots=True)
class AzureSprintUrlParts:
    organization: str
    project: str
    team: str | None
    team_path: str
    iteration_name: str | None
    iteration_path: str | None
    sprint_url: str


def parse_azure_sprint_url(sprint_url: str) -> AzureSprintUrlParts:
    """Extract org/project/team/iteration from an Azure DevOps sprint URL."""
    parsed = urlparse(sprint_url.strip())
    host = parsed.netloc.lower()
    if parsed.scheme not in {"http", "https"} or not _is_supported_ado_host(host):
        raise ValueError(
            "expected an Azure DevOps URL on https://dev.azure.com or *.visualstudio.com"
        )

    segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
    if host == "dev.azure.com":
        if len(segments) < 2:
            raise ValueError("Azure DevOps sprint URL is missing organization/project segments")
        organization = segments[0]
        project_index = 1
    else:
        organization = _organization_from_host(parsed.netloc)
        project_index = 0
    if len(segments) <= project_index:
        raise ValueError("Azure DevOps sprint URL is missing organization/project segments")
    if "_sprints" not in segments:
        raise ValueError("Azure DevOps sprint URL must contain /_sprints/")

    sprint_index = segments.index("_sprints")
    if sprint_index <= project_index:
        raise ValueError("Azure DevOps sprint URL must include organization and project")

    project = segments[project_index]
    tail = segments[sprint_index + 1 :]
    if tail and tail[0] in {"taskboard", "backlog", "capacity", "board"}:
        tail = tail[1:]

    team = _pick_team_name(tail, project=project)
    iteration_name = _pick_iteration_name(tail, project=project, team=team)
    team_path = "/".join(part for part in (organization, project, team) if part)
    iteration_path = (
        "\\".join(part for part in (project, team, iteration_name) if part)
        if iteration_name
        else None
    )

    return AzureSprintUrlParts(
        organization=organization,
        project=project,
        team=team,
        team_path=team_path,
        iteration_name=iteration_name,
        iteration_path=iteration_path,
        sprint_url=sprint_url.strip(),
    )


def _is_supported_ado_host(host: str) -> bool:
    return host == "dev.azure.com" or host.endswith(".visualstudio.com")


def _organization_from_host(netloc: str) -> str:
    host = netloc.lower()
    if host.endswith(".visualstudio.com"):
        return netloc[: -len(".visualstudio.com")]
    raise ValueError("expected an Azure DevOps host")


def _pick_team_name(tail: list[str], *, project: str) -> str | None:
    filtered = [segment for segment in tail if segment and segment != project]
    if len(filtered) >= 2:
        return filtered[0]
    return filtered[0] if len(filtered) == 1 else None


def _pick_iteration_name(tail: list[str], *, project: str, team: str | None) -> str | None:
    if not tail:
        return None
    filtered = [segment for segment in tail if segment and segment not in {project, team}]
    return filtered[-1] if filtered else None
