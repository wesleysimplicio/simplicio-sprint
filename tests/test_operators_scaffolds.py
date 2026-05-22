"""Smoke tests for the v2 operator scaffolds (auth + transport stubs).

GitHub is exercised in :mod:`tests.test_github_operator` with httpx mocks;
this file covers the eight scaffolds that still raise
``TransportUnavailable("not yet wired")`` from each transport body.
"""

from __future__ import annotations

import pytest

from sendsprint.operators import (
    OPERATOR_CLASSES,
    BaseOperator,
    BitbucketOperator,
    ClickUpOperator,
    GiteeOperator,
    GitLabOperator,
    HermesOperator,
    LinearOperator,
    SlackOperator,
    TransportUnavailable,
    TrelloOperator,
)

# Each tuple drives one parametrized check below:
#   (Operator class, full env mapping that satisfies _api_available,
#    list of env keys that the operator reads — used for the "missing creds" assert)
_STUB_CASES: list[tuple[type[BaseOperator], dict[str, str], list[str]]] = [
    (
        GitLabOperator,
        {"GITLAB_TOKEN": "glpat", "GITLAB_PROJECT": "group/repo"},
        ["GITLAB_TOKEN", "GITLAB_PROJECT"],
    ),
    (
        BitbucketOperator,
        {
            "BITBUCKET_WORKSPACE": "ws",
            "BITBUCKET_REPO": "repo",
            "BITBUCKET_USERNAME": "u",
            "BITBUCKET_APP_PASSWORD": "p",
        },
        [
            "BITBUCKET_WORKSPACE",
            "BITBUCKET_REPO",
            "BITBUCKET_USERNAME",
            "BITBUCKET_APP_PASSWORD",
        ],
    ),
    (
        GiteeOperator,
        {"GITEE_TOKEN": "tk", "GITEE_OWNER": "u", "GITEE_REPO": "r"},
        ["GITEE_TOKEN", "GITEE_OWNER", "GITEE_REPO"],
    ),
    (
        LinearOperator,
        {"LINEAR_API_KEY": "key", "LINEAR_TEAM_ID": "team_1"},
        ["LINEAR_API_KEY", "LINEAR_TEAM_ID"],
    ),
    (
        ClickUpOperator,
        {"CLICKUP_TOKEN": "tk", "CLICKUP_LIST_ID": "1"},
        ["CLICKUP_TOKEN", "CLICKUP_LIST_ID", "CLICKUP_FOLDER_ID"],
    ),
    (
        TrelloOperator,
        {"TRELLO_API_KEY": "k", "TRELLO_API_TOKEN": "t", "TRELLO_BOARD_ID": "b"},
        ["TRELLO_API_KEY", "TRELLO_API_TOKEN", "TRELLO_BOARD_ID", "TRELLO_LIST_ID"],
    ),
    (
        SlackOperator,
        {"SLACK_BOT_TOKEN": "xoxb", "SLACK_CHANNEL_ID": "C123"},
        ["SLACK_BOT_TOKEN", "SLACK_CHANNEL_ID"],
    ),
    (
        HermesOperator,
        {
            "HERMES_TOKEN": "tk",
            "HERMES_BASE_URL": "https://hermes.example.com",
            "HERMES_BOARD_ID": "b1",
        },
        ["HERMES_TOKEN", "HERMES_BASE_URL", "HERMES_BOARD_ID"],
    ),
]


@pytest.mark.parametrize("operator_cls, env, env_keys", _STUB_CASES)
def test_stub_operator_reports_api_unavailable_without_credentials(
    operator_cls: type[BaseOperator],
    env: dict[str, str],
    env_keys: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)
    op = operator_cls()
    assert op._api_available() is False
    with pytest.raises(TransportUnavailable):
        op._read_via_api()


@pytest.mark.parametrize("operator_cls, env, env_keys", _STUB_CASES)
def test_stub_operator_with_credentials_reaches_unwired_transport(
    operator_cls: type[BaseOperator],
    env: dict[str, str],
    env_keys: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    op = operator_cls()
    assert op._api_available() is True

    with pytest.raises(TransportUnavailable) as excinfo:
        op._read_via_api()
    assert "not yet wired" in str(excinfo.value)

    with pytest.raises(TransportUnavailable) as excinfo:
        op._read_via_mcp()
    assert "not yet wired" in str(excinfo.value)

    with pytest.raises(TransportUnavailable) as excinfo:
        op._read_via_playwright()
    assert "not yet wired" in str(excinfo.value)


def test_operator_registry_exposes_every_source() -> None:
    expected = {
        "jira",
        "azuredevops",
        "github",
        "gitlab",
        "bitbucket",
        "gitee",
        "linear",
        "clickup",
        "trello",
        "slack",
        "hermes",
    }
    assert set(OPERATOR_CLASSES) == expected
    for name, cls in OPERATOR_CLASSES.items():
        assert issubclass(cls, BaseOperator), name
