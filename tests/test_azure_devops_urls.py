from __future__ import annotations

import pytest

from sendsprint.azure_devops_urls import parse_azure_sprint_url


def test_parse_azure_sprint_url_extracts_context_from_full_taskboard_url() -> None:
    parts = parse_azure_sprint_url(
        "https://dev.azure.com/DigitalProjects-Americas/ONS-16058-MANUTSIS-FORT/"
        "_sprints/taskboard/Time_019/ONS-16058-MANUTSIS-FORT/Time_019/T019_Sprint_98"
    )

    assert parts.organization == "DigitalProjects-Americas"
    assert parts.project == "ONS-16058-MANUTSIS-FORT"
    assert parts.team == "Time_019"
    assert parts.team_path == "DigitalProjects-Americas/ONS-16058-MANUTSIS-FORT/Time_019"
    assert parts.iteration_name == "T019_Sprint_98"
    assert parts.iteration_path == "ONS-16058-MANUTSIS-FORT\\Time_019\\T019_Sprint_98"


def test_parse_azure_sprint_url_rejects_non_ado_hosts() -> None:
    with pytest.raises(ValueError, match="Azure DevOps URL"):
        parse_azure_sprint_url("https://example.com/org/project/_sprints/taskboard/team/sprint")
