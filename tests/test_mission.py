from sendsprint.mission import Mission, build_mission_handoff


def test_build_mission_handoff_creates_planning_titles_and_validation_focus() -> None:
    handoff = build_mission_handoff(
        Mission(
            objective="Ship the release",
            repos=["repo-a", "repo-b"],
            constraints=["release safety"],
        )
    )
    assert handoff.execution_order == ["repo-a", "repo-b"]
    assert "evidence review" in handoff.validation_focus
