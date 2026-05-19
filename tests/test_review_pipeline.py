from sendsprint.review_pipeline import default_review_pipeline


def test_default_review_pipeline_assigns_distinct_roles() -> None:
    pipeline = default_review_pipeline("#48")
    assert [assignment.role for assignment in pipeline.assignments] == [
        "implementer",
        "reviewer",
        "validator",
        "security",
    ]
    assert "reviewer" in pipeline.blocking_roles()
