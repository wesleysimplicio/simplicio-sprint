"""Render sprint data into the simplicio-mapper ``.specs/`` task format."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from sendsprint.models.sprint import Sprint, SprintItem

# Ticket statuses (any source/language) folded into the mapper's three states.
_DONE = {
    "done",
    "closed",
    "resolved",
    "completed",
    "fechado",
    "concluído",
    "concluida",
    "cerrado",
    "terminado",
}
_DOING = {
    "in progress",
    "doing",
    "in review",
    "review",
    "active",
    "started",
    "em andamento",
    "em revisão",
    "em revisao",
    "en progreso",
}


@dataclass
class MaterializedSprint:
    """Paths written when a sprint is rendered into ``.specs/``."""

    sprint_dir: Path
    sprint_md: Path
    backlog_md: Path
    tasks: list[Path] = field(default_factory=list)


class MapperAdapter:
    """Write a :class:`Sprint` (or single item) into simplicio-mapper specs.

    Files land under ``<repo_root>/<specs_dir>/sprints/<sprint-dir>/``. The
    adapter only writes inside the mapper's write-whitelist (``.specs/**``); it
    never touches source files.
    """

    def __init__(self, repo_root: str | Path, *, specs_dir: str = ".specs") -> None:
        self.repo_root = Path(repo_root)
        self.specs_dir = specs_dir

    # -- public API ---------------------------------------------------------

    def sprints_root(self) -> Path:
        return self.repo_root / self.specs_dir / "sprints"

    def sprint_dir_name(self, sprint: Sprint) -> str:
        """``sprint-01`` when the id is numeric, else ``sprint-<slug>``."""
        raw = (sprint.id or sprint.name or "01").strip()
        if raw.isdigit():
            return f"sprint-{int(raw):02d}"
        slug = _slug(raw, max_len=32)
        return slug if slug.startswith("sprint") else f"sprint-{slug}"

    def task_filename(self, item: SprintItem, index: int) -> str:
        return f"{index:02d}-{_slug(item.title or item.key or 'task')}.task.md"

    def materialize_sprint(self, sprint: Sprint) -> MaterializedSprint:
        """Write SPRINT.md, BACKLOG.md and every item task file for ``sprint``."""
        sprint_dir = self.sprints_root() / self.sprint_dir_name(sprint)
        sprint_dir.mkdir(parents=True, exist_ok=True)

        sprint_md = sprint_dir / "SPRINT.md"
        sprint_md.write_text(self.render_sprint(sprint), encoding="utf-8")

        backlog_md = self.sprints_root() / "BACKLOG.md"
        backlog_md.write_text(self.render_backlog(sprint), encoding="utf-8")

        tasks: list[Path] = []
        for index, item in enumerate(sprint.items, start=1):
            path = sprint_dir / self.task_filename(item, index)
            path.write_text(self.render_task(sprint, item, index), encoding="utf-8")
            tasks.append(path)
        return MaterializedSprint(
            sprint_dir=sprint_dir, sprint_md=sprint_md, backlog_md=backlog_md, tasks=tasks
        )

    def write_item(self, item: SprintItem, *, sprint: Sprint | None = None, index: int = 1) -> Path:
        """Write one item's task file (and a SPRINT.md if absent). Returns its path."""
        sprint = sprint or Sprint(
            id="adhoc", name="SendSprint delivery", source="github", items=[item]
        )
        sprint_dir = self.sprints_root() / self.sprint_dir_name(sprint)
        sprint_dir.mkdir(parents=True, exist_ok=True)
        sprint_md = sprint_dir / "SPRINT.md"
        if not sprint_md.exists():
            sprint_md.write_text(self.render_sprint(sprint), encoding="utf-8")
        path = sprint_dir / self.task_filename(item, index)
        path.write_text(self.render_task(sprint, item, index), encoding="utf-8")
        return path

    # -- renderers ----------------------------------------------------------

    def render_task(self, sprint: Sprint, item: SprintItem, index: int) -> str:
        task_id = _task_id(item, index)
        title = (item.title or item.key or task_id).strip()
        owner = f"@{item.assignee}" if item.assignee else "@team"
        status = _map_status(item.status)
        sprint_name = self.sprint_dir_name(sprint)

        front = "\n".join(
            [
                "---",
                f"id: {task_id}",
                f"title: {title}",
                f"sprint: {sprint_name}",
                f"owner: {owner}",
                f"status: {status}",
                f"source_key: {item.key or item.id}",
                "---",
            ]
        )

        context = (
            item.description.strip()
            if item.description
            else f"Deliver “{title}” as specified by the source ticket."
        )
        origin = (
            f"Origin: {item.source_url}" if item.source_url else f"Origin: {item.key or item.id}"
        )

        return "\n".join(
            [
                front,
                "",
                f"# {task_id} — {title}",
                "",
                "## Contexto",
                "",
                context,
                "",
                origin,
                "",
                "## Acceptance Criteria",
                "",
                _render_acceptance(item),
                "",
                "## Out of scope",
                "",
                "- Only what this card requires; anything tangential becomes a new backlog item.",
                "",
                "## Test plan",
                "",
                "### Unit",
                "",
                "- [ ] Cover the new/changed behaviour with valid and invalid inputs.",
                "- [ ] Keep existing tests green; mock external dependencies.",
                "",
                "### Integration",
                "",
                "- [ ] Exercise the happy path plus at least one error path end to end.",
                "",
                "### End-to-end",
                "",
                "- [ ] Capture evidence (test run + screenshot when UI is touched) for the PR.",
                "",
                "## Definition of Done",
                "",
                "- [ ] All Acceptance Criteria met and verified.",
                "- [ ] Tests green locally and in CI.",
                "- [ ] Draft PR opened linking this task and the source ticket.",
                "- [ ] Status updated in BACKLOG.md and SPRINT.md.",
                "",
                "## Links",
                "",
                _render_links(sprint_name, item),
                "",
            ]
        )

    def render_sprint(self, sprint: Sprint) -> str:
        name = sprint.name or self.sprint_dir_name(sprint)
        status = _map_status(sprint.state)
        rows = ["| File | Status | Owner |", "| --- | --- | --- |"]
        for index, item in enumerate(sprint.items, start=1):
            owner = f"@{item.assignee}" if item.assignee else "@team"
            rows.append(
                f"| `{self.task_filename(item, index)}` | {_map_status(item.status)} | {owner} |"
            )
        return "\n".join(
            [
                "---",
                f"sprint: {self.sprint_dir_name(sprint)}",
                f"status: {status}",
                f"source: {sprint.source}",
                "---",
                "",
                f"# {name}",
                "",
                "## Objetivo",
                "",
                sprint.goal or f"Deliver the {len(sprint.items)} card(s) scoped into this sprint.",
                "",
                "## Tasks da sprint",
                "",
                *rows,
                "",
            ]
        )

    def render_backlog(self, sprint: Sprint) -> str:
        rows = ["| # | Item | Status | Owner |", "| --- | --- | --- | --- |"]
        for index, item in enumerate(sprint.items, start=1):
            owner = f"@{item.assignee}" if item.assignee else "@team"
            title = (item.title or item.key or f"item {index}").replace("|", "\\|")
            rows.append(f"| {index} | {title} | {_map_status(item.status)} | {owner} |")
        return "\n".join(["# Backlog", "", *rows, ""])


# -- helpers ----------------------------------------------------------------


def _map_status(status: str | None) -> str:
    value = (status or "").strip().lower()
    if value in _DONE:
        return "done"
    if value in _DOING:
        return "doing"
    return "todo"


def _task_id(item: SprintItem, index: int) -> str:
    key = (item.key or item.id or "").strip()
    if key:
        return f"TASK-{re.sub(r'[^A-Za-z0-9]+', '-', key).strip('-').upper()}"
    return f"TASK-{index:03d}"


def _render_acceptance(item: SprintItem) -> str:
    text = (item.acceptance_criteria or "").strip()
    if not text:
        return f"- [ ] AC-1 — {item.title or item.key} is implemented and verified by a test."
    lines: list[str] = []
    n = 0
    for raw in text.splitlines():
        stripped = raw.strip().lstrip("-*•").strip()
        if not stripped:
            continue
        stripped = re.sub(r"^\[[ xX]\]\s*", "", stripped)
        n += 1
        lines.append(f"- [ ] AC-{n} — {stripped}")
    return (
        "\n".join(lines)
        if lines
        else (f"- [ ] AC-1 — {item.title or item.key} is implemented and verified by a test.")
    )


def _render_links(sprint_name: str, item: SprintItem) -> str:
    links = [
        f"- Sprint: `.specs/sprints/{sprint_name}/SPRINT.md`",
        "- Backlog: `.specs/sprints/BACKLOG.md`",
    ]
    if item.source_url:
        links.append(f"- Ticket: {item.source_url}")
    if item.key:
        links.append(f"- Source key: `{item.key}`")
    if item.labels:
        links.append(f"- Labels: {', '.join(item.labels)}")
    return "\n".join(links)


def _slug(text: str, *, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].strip("-") or "task"
