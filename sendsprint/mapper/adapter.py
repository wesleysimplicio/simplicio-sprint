"""Render sprint data into the simplicio-mapper ``.specs/`` task format."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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

PROJECT_MAP_REL = Path(".simplicio/project-map.json")
PRECEDENT_INDEX_REL = Path(".simplicio/precedent-index.json")


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

    def load_structured_context(self) -> dict[str, Any]:
        """Load mapper-generated project and precedent artifacts when present."""
        return {
            "project_map": _read_json(self.repo_root / PROJECT_MAP_REL),
            "precedent_index": _read_json(self.repo_root / PRECEDENT_INDEX_REL),
        }

    def mapper_context_for_item(
        self,
        item: SprintItem,
        *,
        max_files: int = 6,
        max_precedents: int = 4,
    ) -> dict[str, Any]:
        """Return ranked mapper context for a sprint item.

        The shape is intentionally plain JSON so it can be passed directly to
        simplicio-cli, simplicio-prompt or evidence manifests without importing
        mapper internals.
        """
        artifacts = self.load_structured_context()
        project_map = artifacts.get("project_map") or {}
        precedent_index = artifacts.get("precedent_index") or {}
        if not project_map and not precedent_index:
            return {}

        terms = set(_tokens(_item_text(item)))
        recent_changes = project_map.get("recent_changes") or []
        changed_files = {
            str(entry.get("path") if isinstance(entry, dict) else entry)
            for entry in (project_map.get("changed_files") or [])
        }
        changed_files.update(
            str(entry.get("path"))
            for entry in recent_changes
            if isinstance(entry, dict) and entry.get("path")
        )

        files = _rank_files(project_map.get("files") or [], terms, changed_files, max_files)
        precedents = _rank_precedents(
            precedent_index.get("items") or [], terms, {f["path"] for f in files}, max_precedents
        )
        context: dict[str, Any] = {
            "artifact_schema": {
                "project_map": project_map.get("schema"),
                "precedent_index": precedent_index.get("schema"),
            },
            "product": project_map.get("product") or {},
            "architecture": project_map.get("architecture") or {},
            "relevant_files": files,
            "precedents": precedents,
            "recent_changes": [
                entry for entry in recent_changes if isinstance(entry, dict) and entry.get("path")
            ][:8],
            "artifact_paths": {
                "project_map": str(PROJECT_MAP_REL),
                "precedent_index": str(PRECEDENT_INDEX_REL),
            },
        }
        return {key: value for key, value in context.items() if value not in ({}, [], None)}

    def structured_context_for_item(
        self,
        item: SprintItem,
        *,
        max_files: int = 6,
        max_precedents: int = 4,
    ) -> str:
        """Render mapper artifacts as compact markdown for task specs/prompts."""
        context = self.mapper_context_for_item(
            item, max_files=max_files, max_precedents=max_precedents
        )
        if not context:
            return ""

        lines: list[str] = []
        product = context.get("product") or {}
        if product:
            stack = f" ({product.get('stack')})" if product.get("stack") else ""
            lines.append(f"- Product: {product.get('name', 'project')}{stack}")
        architecture = context.get("architecture") or {}
        signals = architecture.get("signals") or []
        if signals:
            lines.append(f"- Architecture signals: {', '.join(map(str, signals[:8]))}")
        if architecture.get("system_type"):
            lines.append(f"- System type: {architecture['system_type']}")

        files = context.get("relevant_files") or []
        if files:
            lines.append("")
            lines.append("### Relevant files")
            for file in files:
                roles = f" [{', '.join(file.get('roles') or [])}]" if file.get("roles") else ""
                exports = (
                    f" exports: {', '.join(file.get('exports') or [])}"
                    if file.get("exports")
                    else ""
                )
                lines.append(f"- `{file['path']}`{roles}{exports}")

        changes = context.get("recent_changes") or []
        if changes:
            lines.append("")
            lines.append("### Recent mapper changes")
            for change in changes[:6]:
                lines.append(f"- `{change['path']}` ({change.get('status', 'modified')})")

        precedents = context.get("precedents") or []
        if precedents:
            lines.append("")
            lines.append("### Precedent candidates")
            for precedent in precedents:
                location = f"{precedent['path']}:{precedent.get('line', 1)}"
                summary = precedent.get("summary") or precedent.get("change_type") or "precedent"
                lines.append(f"- `{location}` - {summary}")
        return "\n".join(lines)

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
        structured_context = self.structured_context_for_item(item)
        structured_section = (
            [
                "## Structured mapper context",
                "",
                structured_context,
                "",
            ]
            if structured_context
            else []
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
                *structured_section,
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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _item_text(item: SprintItem) -> str:
    return "\n".join(
        [
            item.key or "",
            item.title or "",
            item.description or "",
            item.acceptance_criteria or "",
            " ".join(item.labels or []),
        ]
    )


def _tokens(value: object) -> list[str]:
    text = str(value or "")
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [
        token.lower()
        for token in re.split(r"[^A-Za-z0-9]+", text)
        if len(token) > 2
        and token.lower()
        not in {
            "the",
            "and",
            "for",
            "with",
            "from",
            "task",
            "tests",
            "test",
            "src",
            "app",
        }
    ]


def _rank_files(
    files: Iterable[Any], terms: set[str], changed_files: set[str], limit: int
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for raw in files:
        if not isinstance(raw, dict) or not raw.get("path"):
            continue
        path = str(raw["path"])
        haystack = " ".join(
            [
                path,
                str(raw.get("language") or ""),
                " ".join(map(str, raw.get("roles") or [])),
                " ".join(map(str, raw.get("exports") or [])),
                " ".join(map(str, raw.get("imports") or [])),
            ]
        )
        overlap = len(terms.intersection(_tokens(haystack)))
        changed = path in changed_files
        if not overlap and not changed:
            continue
        score = (overlap * 3.0) + (1.5 if changed else 0.0) + float(raw.get("importance") or 0)
        ranked.append((score, raw))

    ranked.sort(key=lambda item: (-item[0], str(item[1].get("path"))))
    result: list[dict[str, Any]] = []
    for score, raw in ranked[:limit]:
        result.append(
            {
                "path": str(raw["path"]),
                "language": raw.get("language"),
                "roles": list(raw.get("roles") or [])[:6],
                "exports": list(raw.get("exports") or [])[:6],
                "imports": list(raw.get("imports") or [])[:6],
                "score": round(score, 3),
            }
        )
    return result


def _rank_precedents(
    items: Iterable[Any], terms: set[str], relevant_paths: set[str], limit: int
) -> list[dict[str, Any]]:
    ranked: list[tuple[float, dict[str, Any]]] = []
    for raw in items:
        if not isinstance(raw, dict) or not raw.get("path"):
            continue
        path = str(raw["path"])
        haystack = " ".join(
            [
                path,
                str(raw.get("change_type") or ""),
                str(raw.get("summary") or ""),
                str(raw.get("snippet") or ""),
                " ".join(map(str, raw.get("tags") or [])),
            ]
        )
        overlap = len(terms.intersection(_tokens(haystack)))
        path_bonus = 2.0 if path in relevant_paths else 0.0
        if not overlap and not path_bonus:
            continue
        score = (overlap * 2.0) + path_bonus
        ranked.append((score, raw))

    ranked.sort(
        key=lambda item: (-item[0], str(item[1].get("path")), int(item[1].get("line") or 0))
    )
    result: list[dict[str, Any]] = []
    for score, raw in ranked[:limit]:
        result.append(
            {
                "id": raw.get("id"),
                "path": str(raw["path"]),
                "line": int(raw.get("line") or 1),
                "change_type": raw.get("change_type"),
                "tags": list(raw.get("tags") or [])[:8],
                "summary": raw.get("summary"),
                "score": round(score, 3),
            }
        )
    return result


def _slug(text: str, *, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].strip("-") or "task"
