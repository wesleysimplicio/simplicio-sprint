from sendsprint.ci_repair import CheckRunFailure, plan_ci_repair


def test_plan_ci_repair_identifies_test_failures() -> None:
    plan = plan_ci_repair(
        [CheckRunFailure(name="Playwright", conclusion="failure", log_excerpt="playwright timeout")]
    )
    assert plan.root_cause == "test failure"
    assert "npx playwright test" in plan.rerun_commands
