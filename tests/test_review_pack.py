from sendsprint.review_pack import HumanReviewPack


def test_human_review_pack_renders_markdown_sections() -> None:
    body = HumanReviewPack(
        summary="Safe change",
        changed_areas=["sendsprint/cli.py"],
        test_commands=["pytest tests -q"],
        evidence_links=["https://example.com/evidence/1"],
        rollback_plan="Delete branch if needed.",
    ).to_markdown()
    assert "Human Review Pack" in body
    assert "pytest tests -q" in body
