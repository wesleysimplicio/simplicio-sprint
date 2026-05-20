from sendsprint.runtime_readiness import (
    build_cross_stack_runtime_readiness,
    format_runtime_readiness_markdown,
)


def test_cross_stack_runtime_readiness_is_ready_for_repo() -> None:
    report = build_cross_stack_runtime_readiness(".")

    assert report.status == "ready"
    keys = {criterion.key for criterion in report.criteria}
    assert {
        "architecture-decision",
        "python-control-plane-contract",
        "go-worker-non-blocking-boundary",
        "rust-accelerator-benchmark-gate",
        "node-dashboard-operator-loop",
        "windows-copilot-happy-path",
        "child-validation-and-rollback",
        "resource-aware-fanout",
    } <= keys
    assert all(criterion.passed for criterion in report.criteria)


def test_runtime_readiness_markdown_lists_boundaries_and_criteria() -> None:
    report = build_cross_stack_runtime_readiness(".")

    rendered = format_runtime_readiness_markdown(report)

    assert "Status: **ready**" in rendered
    assert "| python | control plane |" in rendered
    assert "`go-worker-non-blocking-boundary`" in rendered
