import pytest
from pydantic import ValidationError

from sendsprint.oss_mode import (
    OssValidationPlan,
    build_oss_candidate,
    build_oss_publish_plan,
    build_oss_snapshot,
    build_oss_validation_plan,
    check_oss_dedupe,
    detect_oss_mode,
)


def test_detect_oss_mode_reads_common_repo_conventions(tmp_path) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text("rules", encoding="utf-8")
    (tmp_path / "CODE_OF_CONDUCT.md").write_text("rules", encoding="utf-8")
    (tmp_path / "SECURITY.md").write_text("rules", encoding="utf-8")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(
        "template",
        encoding="utf-8",
    )

    mode = detect_oss_mode(tmp_path)

    assert mode.has_contributing is True
    assert mode.has_pr_template is True


def test_detect_oss_mode_reads_pr_template_directory(tmp_path) -> None:
    template_dir = tmp_path / ".github" / "PULL_REQUEST_TEMPLATE"
    template_dir.mkdir(parents=True)
    (template_dir / "bugfix.md").write_text("template", encoding="utf-8")

    mode = detect_oss_mode(tmp_path)

    assert mode.has_pr_template is True


def test_build_oss_snapshot_detects_branch_and_test_commands(tmp_path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/develop\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest"}}', encoding="utf-8")
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "package.json").write_text('{"scripts":{"test":"vitest"}}', encoding="utf-8")

    snapshot = build_oss_snapshot(tmp_path)

    assert snapshot.repo_path == str(tmp_path.resolve())
    assert snapshot.default_branch == "develop"
    assert snapshot.test_commands == [
        "python -m pytest tests/ -q",
        "npm test",
        "npm --prefix web test",
    ]


def test_check_oss_dedupe_blocks_memory_and_public_ref_overlap(tmp_path) -> None:
    snapshot = build_oss_snapshot(tmp_path)
    candidate = build_oss_candidate(
        snapshot,
        title="Fix NameError in conversation loop",
        issue_url="https://github.com/NousResearch/hermes-agent/issues/27370",
        dedupe_markers=[
            "nameerror in conversation loop",
            "bare _pool_may_recover_from_rate_limit call",
        ],
    )

    decision = check_oss_dedupe(
        candidate,
        existing_refs=["PR #27359 fixes NameError in conversation loop"],
        memory_markers={"bare _pool_may_recover_from_rate_limit call": "PR #28297"},
    )

    assert decision.status == "blocked"
    assert "PR #27359 fixes NameError in conversation loop" in decision.evidence
    assert "PR #28297" in decision.evidence


def test_build_oss_publish_plan_blocks_until_validation_passes(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    snapshot = build_oss_snapshot(tmp_path)
    candidate = build_oss_candidate(snapshot, title="Fix CLI status output")

    validation = build_oss_validation_plan(snapshot, ["sendsprint/oss_mode.py"])
    blocked = build_oss_publish_plan(candidate, validation)
    ready = build_oss_publish_plan(candidate, validation.model_copy(update={"passed": True}))

    assert blocked.blocked is True
    assert blocked.reason == "validation evidence is required before publishing"
    assert ready.blocked is False


def test_oss_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        OssValidationPlan(commands=[], unexpected=True)  # type: ignore[call-arg]
