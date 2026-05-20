"""Tests for deterministic sprint item task understanding."""

from __future__ import annotations

from datetime import UTC, datetime

from sendsprint.models.sprint import Attachment, Comment, SprintItem
from sendsprint.models.workspace import RepoConfig, WorkspaceConfig
from sendsprint.task_understanding import understand_sprint_item


def _workspace() -> WorkspaceConfig:
    return WorkspaceConfig(
        root_path="/tmp/workspace",
        repos=[
            RepoConfig(name="web", path="apps/web", role="front", tech="react"),
            RepoConfig(name="api", path="services/api", role="api", tech="fastapi"),
            RepoConfig(name="infra", path="infra", role="infra", tech="terraform"),
            RepoConfig(name="docs", path="docs", role="other"),
        ],
    )


def _item(
    *,
    key: str = "SHOP-123",
    item_type: str = "Task",
    title: str,
    description: str | None = None,
    acceptance_criteria: str | None = None,
    labels: list[str] | None = None,
    comments: list[str] | None = None,
    attachments: list[str] | None = None,
    parent_key: str | None = None,
) -> SprintItem:
    return SprintItem(
        id=key,
        key=key,
        type=item_type,  # type: ignore[arg-type]
        title=title,
        description=description,
        status="New",
        labels=labels or [],
        comments=[
            Comment(author="dev", body=body, created_at=datetime.now(UTC))
            for body in comments or []
        ],
        attachments=[
            Attachment(filename=filename, url=f"https://example.test/{filename}")
            for filename in attachments or []
        ],
        acceptance_criteria=acceptance_criteria,
        parent_key=parent_key,
    )


def test_understands_frontend_item_from_ui_signals() -> None:
    report = understand_sprint_item(
        _item(
            title="Fix checkout modal layout",
            description="The dashboard form button overlaps the confirmation screen for users.",
            acceptance_criteria="- User can submit the checkout form from the modal",
            labels=["scope:front", "project:checkout"],
            attachments=["checkout-screenshot.png"],
        ),
        _workspace(),
    )

    assert report.project == "checkout"
    assert report.surfaces == ["front"]
    assert "frontend-ui" in report.capabilities
    assert report.likely_repos == ["web"]
    assert "playwright-e2e" in report.validation_needs
    assert "screenshot-evidence" in report.validation_needs
    assert report.confidence >= 0.7
    assert report.requires_confirmation is False
    assert any(signal.startswith("title:modal") for signal in report.signals["front"])


def test_understands_backend_item_from_endpoint_and_comment_signals() -> None:
    report = understand_sprint_item(
        _item(
            key="BILL-77",
            title="Add invoice status endpoint",
            description="Persist the invoice status in the database and return it from the API.",
            acceptance_criteria="API returns the stored status for paid invoices",
            labels=["scope:back"],
            comments=["Staging error shows the service drops the database response."],
        ),
        _workspace(),
    )

    assert report.project == "BILL"
    assert report.surfaces == ["back"]
    assert {"backend-api", "data"}.issubset(set(report.capabilities))
    assert report.likely_repos == ["api"]
    assert "integration-tests" in report.validation_needs
    assert "api-contract-tests" in report.validation_needs
    assert any(signal.startswith("comments:service") for signal in report.signals["back"])
    assert report.requires_confirmation is False


def test_understands_full_stack_item_from_front_and_back_signals() -> None:
    report = understand_sprint_item(
        _item(
            title="Add onboarding form and API endpoint",
            description=(
                "Create the React form, submit it to the backend service, and persist the "
                "new account record."
            ),
            acceptance_criteria=(
                "- User completes onboarding in the browser\n"
                "- API saves the account and returns the created response"
            ),
            labels=["feature:onboarding"],
        ),
        _workspace(),
    )

    assert report.surfaces == ["front", "back", "full-stack"]
    assert {"frontend-ui", "backend-api"}.issubset(set(report.capabilities))
    assert report.likely_repos == ["web", "api"]
    assert {"playwright-e2e", "integration-tests"}.issubset(set(report.validation_needs))
    assert any("both front and back" in reason for reason in report.reasons)
    assert report.requires_confirmation is False


def test_understands_docs_item_from_readme_and_guide_signals() -> None:
    report = understand_sprint_item(
        _item(
            key="DOCS-9",
            title="Update README setup guide",
            description="Document the local install command and refresh the tutorial example.",
            acceptance_criteria="README example is accurate and runnable",
            labels=["type:docs"],
            attachments=["setup-guide.md"],
        ),
        _workspace(),
    )

    assert report.project == "DOCS"
    assert report.surfaces == ["docs"]
    assert "documentation" in report.capabilities
    assert report.likely_repos == ["docs"]
    assert report.validation_needs == ["docs-smoke", "acceptance-criteria-check"]
    assert report.requires_confirmation is False


def test_understands_infra_item_from_pipeline_and_deploy_signals() -> None:
    report = understand_sprint_item(
        _item(
            key="OPS-41",
            title="Fix GitHub Actions deploy pipeline",
            description=(
                "The Docker deployment workflow should validate Terraform configuration "
                "before publishing."
            ),
            acceptance_criteria="Pipeline blocks invalid Terraform config before deploy",
            labels=["scope:infra"],
        ),
        _workspace(),
    )

    assert report.project == "OPS"
    assert report.surfaces == ["infra"]
    assert "deployment-infra" in report.capabilities
    assert report.likely_repos == ["infra"]
    assert "configuration-validation" in report.validation_needs
    assert "pipeline-dry-run" in report.validation_needs
    assert report.requires_confirmation is False


def test_low_confidence_item_requires_confirmation() -> None:
    report = understand_sprint_item(
        _item(
            key="179500",
            title="Do the thing",
            description=None,
            labels=[],
            parent_key="PLAT-12",
        ),
        _workspace(),
    )

    assert report.project == "PLAT"
    assert report.surfaces == []
    assert report.capabilities == ["implementation"]
    assert report.likely_repos == []
    assert report.confidence < 0.55
    assert report.requires_confirmation is True
    assert "manual-confirmation" in report.validation_needs
    assert report.signals["parent_key"] == ["PLAT-12"]
