from sendsprint.validation_planner import build_validation_plan


def test_validation_plan_stages_python_changes_by_risk() -> None:
    plan = build_validation_plan(
        issue_text="update api config",
        changed_files=["sendsprint/api/routes/runs.py"],
    )
    assert plan.risk == "medium"
    assert [stage.name for stage in plan.stages] == ["focused", "regression"]


def test_validation_plan_adds_evidence_stage_for_high_risk() -> None:
    plan = build_validation_plan(
        issue_text="update release workflow and deploy config",
        changed_files=[".github/workflows/release.yml"],
    )
    assert plan.risk == "high"
    assert [stage.name for stage in plan.stages][-1] == "evidence"
