"""Cached template rendering for sprint planning artifacts."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from string import Template
from typing import Any

from sendsprint.utils.cache import CacheStats, LruTtlCache
from sendsprint.utils.json import dumps_json, dumps_json_bytes

DEFAULT_TEMPLATES: dict[str, str] = {
    "sprint": """---
sprint: $sprint_slug
status: $status
source: $source
---

# $name

## Objetivo

$goal

## Tasks da sprint

$task_rows
""",
    "backlog": """# Backlog

$rows
""",
    "retrospective": """# Retrospective — $name

## Snapshot

- Sprint: `$sprint_slug`
- Sprint ID: `$sprint_id`
- Source: `$source`
- Status: `$status`
- Items: $item_count
- Done: $done_count
- Doing: $doing_count
- Todo: $todo_count

## Review prompts

- [ ] What shipped and has evidence?
- [ ] What was blocked or carried over?
- [ ] Which mapper/context signals should be reused next sprint?
- [ ] Which LLM/fan-out plan outputs were useful enough to keep?

## Tasks

$task_rows

## Notes

$notes
""",
}


class TemplateRenderer:
    """Render named templates with cached compiled and rendered artifacts."""

    def __init__(
        self,
        templates: Mapping[str, str] | None = None,
        *,
        maxsize: int = 128,
        ttl_s: float | None = 3600,
    ) -> None:
        self._templates = dict(DEFAULT_TEMPLATES)
        if templates:
            self._templates.update(templates)
        self._compiled = LruTtlCache[str, Template](maxsize=maxsize, ttl_s=ttl_s)
        self._rendered = LruTtlCache[str, str](maxsize=maxsize, ttl_s=ttl_s)

    def register(self, name: str, template: str) -> None:
        """Register or replace a template."""
        self._templates[name] = template
        self._compiled.set(name, Template(template))

    def render(self, name: str, values: Mapping[str, Any] | None = None) -> str:
        """Render a named template and memoize identical renders."""
        values = values or {}
        key = self._render_key(name, values)
        return self._rendered.get_or_set(
            key,
            lambda: self._template(name).safe_substitute(_text(values)),
        )

    def compiled_stats(self) -> CacheStats:
        """Return compiled-template cache counters."""
        return self._compiled.stats()

    def rendered_stats(self) -> CacheStats:
        """Return rendered-output cache counters."""
        return self._rendered.stats()

    def _template(self, name: str) -> Template:
        try:
            raw = self._templates[name]
        except KeyError as exc:
            raise KeyError(f"template not registered: {name}") from exc
        return self._compiled.get_or_set(name, lambda: Template(raw))

    def _render_key(self, name: str, values: Mapping[str, Any]) -> str:
        payload = {
            "name": name,
            "template": self._templates.get(name, ""),
            "values": values,
        }
        encoded = dumps_json_bytes(payload, sort_keys=True, default=str)
        return hashlib.blake2b(encoded, digest_size=16).hexdigest()


def _text(values: Mapping[str, Any]) -> dict[str, str]:
    return {key: _stringify(value) for key, value in values.items()}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return dumps_json(value, sort_keys=True, default=str)
