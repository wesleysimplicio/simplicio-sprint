"""Tests for User Story decomposition into front/back tasks."""

from sendsprint.agents.story_task_planner import delivery_items, item_matches_repo, plan_story_tasks
from sendsprint.models.sprint import Sprint, SprintItem
from sendsprint.models.workspace import RepoConfig, WorkspaceConfig


def _story() -> SprintItem:
    return SprintItem(
        id="179500",
        key="179500",
        type="Story",
        title="Criar filtro de Raiz ou CNPJ",
        status="New",
        description="Adicionar filtro na tela de envio de emails.",
    )


def _sprint(items: list[SprintItem]) -> Sprint:
    return Sprint(id="Sprint 29", name="Sprint 29", source="azuredevops", items=items)


def test_plan_story_tasks_creates_front_and_back_tasks_when_story_has_no_tasks() -> None:
    ws = WorkspaceConfig(
        root_path="/tmp",
        repos=[
            RepoConfig(name="api", path="api", role="api"),
            RepoConfig(name="web", path="web", role="front"),
        ],
    )

    sprint, report = plan_story_tasks(_sprint([_story()]), ws)

    generated = [item for item in sprint.items if "sendsprint:generated" in item.labels]
    assert report.status == "ok"
    assert [item.key for item in generated] == ["179500-FRONT", "179500-BACK"]
    assert all(item.parent_key == "179500" for item in generated)


def test_plan_story_tasks_skips_story_when_child_task_exists() -> None:
    child = SprintItem(
        id="1",
        key="1",
        type="Task",
        title="Front task",
        status="New",
        parent_key="179500",
    )

    sprint, report = plan_story_tasks(_sprint([_story(), child]))

    assert report.status == "skipped"
    assert sprint.items == [_story(), child]


def test_delivery_items_skips_parent_story_with_child_tasks() -> None:
    sprint, _ = plan_story_tasks(_sprint([_story()]))

    deliverable = delivery_items(sprint)

    assert [item.key for item in deliverable] == ["179500-FRONT", "179500-BACK"]


def test_item_matches_repo_routes_generated_tasks_by_scope() -> None:
    sprint, _ = plan_story_tasks(_sprint([_story()]))
    front = next(item for item in sprint.items if item.key.endswith("-FRONT"))
    back = next(item for item in sprint.items if item.key.endswith("-BACK"))

    assert item_matches_repo(front, "front") is True
    assert item_matches_repo(front, None) is True
    assert item_matches_repo(front, "api") is False
    assert item_matches_repo(back, "api") is True
    assert item_matches_repo(back, "front") is False
