"""Extract reviewable task candidates from meeting transcripts."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

TASK_MARKERS = (
    "action",
    "todo",
    "task",
    "tarefa",
    "ação",
    "acao",
    "encaminhamento",
    "precisamos",
    "we need",
    "vamos",
    "must",
    "should",
)

SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|senha|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_.-]{12,}"),
)


class TranscriptSourceRef(BaseModel):
    """Line-based source traceability for an extracted candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    line_start: int
    line_end: int
    excerpt: str


class TranscriptTaskCandidate(BaseModel):
    """Reviewable task candidate extracted from a transcript."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    summary: str
    owner: str | None = None
    priority: str | None = None
    due_date: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    source_refs: list[TranscriptSourceRef] = Field(default_factory=list)
    sensitive: bool = False


@dataclass(frozen=True)
class _RawCandidate:
    line: int
    text: str


def extract_task_candidates(
    transcript: str,
    *,
    existing_titles: Iterable[str] | None = None,
) -> list[TranscriptTaskCandidate]:
    """Extract deduplicated task candidates from Portuguese/English transcripts."""
    existing = {_normalize(title) for title in existing_titles or []}
    seen: set[str] = set()
    candidates: list[TranscriptTaskCandidate] = []
    raw = [_RawCandidate(i, line.strip()) for i, line in enumerate(transcript.splitlines(), 1)]
    for item in raw:
        if not item.text or not _looks_like_task(item.text):
            continue
        redacted, sensitive = redact_sensitive(item.text)
        title = _title_from_line(redacted)
        norm = _normalize(title)
        if not norm or norm in existing or norm in seen:
            continue
        seen.add(norm)
        candidates.append(
            TranscriptTaskCandidate(
                title=title,
                summary=redacted,
                owner=_extract_owner(redacted),
                priority=_extract_priority(redacted),
                due_date=_extract_due(redacted),
                acceptance_criteria=_extract_acceptance(redacted),
                dependencies=_extract_list(redacted, ("depends on", "dependência", "depende de")),
                risks=_extract_list(redacted, ("risk", "risco")),
                source_refs=[
                    TranscriptSourceRef(line_start=item.line, line_end=item.line, excerpt=redacted)
                ],
                sensitive=sensitive,
            )
        )
    return candidates


def redact_sensitive(text: str) -> tuple[str, bool]:
    """Redact secrets while preserving enough context for review."""
    sensitive = False
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(redacted):
            sensitive = True
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted, sensitive


def _looks_like_task(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in TASK_MARKERS)


def _title_from_line(line: str) -> str:
    text = re.sub(
        r"^[A-Za-zÀ-ÿ0-9_. -]{1,40}:\s+"
        r"(?=(action|todo|task|tarefa|ação|acao|precisamos|we need|vamos|must|should))",
        "",
        line,
        flags=re.I,
    )
    text = re.sub(r"^\s*(action|todo|task|tarefa|ação|acao)\s*[:\-]\s*", "", text, flags=re.I)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    text = re.sub(
        r"\s+(owner|respons[aá]vel|due|prazo|priority|prioridade)\s*[:=].*$",
        "",
        text,
        flags=re.I,
    )
    text = text.strip(" -.;")
    if len(text) > 96:
        text = text[:93].rstrip() + "..."
    return text or "Untitled transcript task"


def _extract_owner(line: str) -> str | None:
    match = re.search(
        r"(?i)(owner|respons[aá]vel)\s*[:=]\s*"
        r"(.+?)(?=\s+(priority|prioridade|due|prazo|acceptance|aceite)\s*[:=]|$)",
        line,
    )
    return match.group(2).strip() if match else None


def _extract_priority(line: str) -> str | None:
    match = re.search(
        r"(?i)(priority|prioridade)\s*[:=]\s*"
        r"(p[0-3]|high|medium|low|alta|média|media|baixa)",
        line,
    )
    return match.group(2).strip() if match else None


def _extract_due(line: str) -> str | None:
    match = re.search(
        r"(?i)(due|prazo)\s*[:=]\s*"
        r"(.+?)(?=\s+(acceptance|aceite|crit[eé]rio|risk|risco)\s*[:=]|$)",
        line,
    )
    return match.group(2).strip() if match else None


def _extract_acceptance(line: str) -> list[str]:
    match = re.search(r"(?i)(acceptance|aceite|crit[eé]rio[s]?)\s*[:=]\s*(.+)$", line)
    if not match:
        return []
    return [
        part.strip(" .")
        for part in re.split(r"\s*\|\s*|\s*;\s*", match.group(2))
        if part.strip()
    ]


def _extract_list(line: str, labels: tuple[str, ...]) -> list[str]:
    label_re = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?i)({label_re})\s*[:=]\s*(.+)$", line)
    if not match:
        return []
    return [
        part.strip(" .")
        for part in re.split(r"\s*,\s*|\s*;\s*", match.group(2))
        if part.strip()
    ]


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
