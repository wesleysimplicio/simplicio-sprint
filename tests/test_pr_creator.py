"""Tests for PrCreator provider payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sendsprint.agents.pr_creator import PrCreator


def test_ado_pr_marks_required_reviewers(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"pullRequestId": 44183}

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            return None

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, url: str, *, json: dict[str, Any], headers: dict[str, str]) -> FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setenv("AZURE_DEVOPS_ORG", "grupointerplayers")
    monkeypatch.setenv("AZURE_DEVOPS_PROJECT", "Produtos InterPlayers")
    monkeypatch.setenv("AZURE_DEVOPS_REPO", "fatura-ip-web")
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "pat")
    monkeypatch.setattr("sendsprint.agents.pr_creator.httpx.Client", FakeClient)

    creator = PrCreator(
        tmp_path,
        provider="azuredevops",
        target_branch="develop",
        reviewers=["optional@example.com"],
        required_reviewers=["daniel.ribeiro_ext@interplayers.com.br"],
    )

    report = creator.create(
        source_branch="bugfix/179851-campos-busca-comportamento-incorreto",
        title="fix: stabilize project search fields",
        body="Refs 179851",
    )

    assert report.status == "ok"
    assert captured["json"]["reviewers"] == [
        {"uniqueName": "optional@example.com"},
        {"uniqueName": "daniel.ribeiro_ext@interplayers.com.br", "isRequired": True},
    ]
    assert captured["json"]["targetRefName"] == "refs/heads/develop"
    assert report.pr is not None
    expected_url = (
        "https://dev.azure.com/grupointerplayers/Produtos InterPlayers"
        "/_git/fatura-ip-web/pullrequest/44183"
    )
    assert report.pr.url == expected_url
