"""Adapt sprint data into the simplicio-mapper ``.specs/`` format.

simplicio-mapper (https://github.com/wesleysimplicio/simplicio-mapper) lays a
project's agent context under ``.specs/``. Sprint execution lives in
``.specs/sprints/sprint-XX/`` as a ``SPRINT.md`` plus one ``NN-slug.task.md`` per
work item, each with YAML frontmatter and the canonical task sections
(Contexto, Acceptance Criteria, Out of scope, Test plan, Definition of Done,
Links). :class:`~sendsprint.mapper.adapter.MapperAdapter` renders a
:class:`~sendsprint.models.sprint.Sprint` into exactly that layout so
simplicio-cli has structured context when it implements each card.
"""

from sendsprint.mapper.adapter import MapperAdapter, MaterializedSprint

__all__ = ["MapperAdapter", "MaterializedSprint"]
