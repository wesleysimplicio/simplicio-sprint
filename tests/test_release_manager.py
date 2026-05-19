from sendsprint.release_manager import ClosedWorkItem, recommend_release


def test_recommend_release_chooses_minor_for_features() -> None:
    recommendation = recommend_release(
        [ClosedWorkItem(title="feat: add planner", labels=["enhancement"])]
    )
    assert recommendation.level == "minor"
