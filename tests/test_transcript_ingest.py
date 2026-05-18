"""Tests for meeting transcript task extraction."""

from __future__ import annotations

from sendsprint.ingest import extract_task_candidates


def test_extracts_portuguese_and_english_action_items() -> None:
    transcript = """
    Wesley: Ação: criar dashboard local Owner: Ana prioridade: alta
    prazo: sexta aceite: lista runs; abre evidência
    John: TODO: add GitHub Issues sync owner: Bob priority: P1
    due: Friday acceptance: comments evidence
    """
    tasks = extract_task_candidates(transcript)
    assert len(tasks) == 2
    assert tasks[0].title == "criar dashboard local"
    assert tasks[0].owner == "Ana"
    assert tasks[1].priority == "P1"
    assert tasks[1].due_date is None


def test_deduplicates_and_redacts_sensitive_content() -> None:
    transcript = """
    TODO: create deploy task token=abc123456789SECRET owner: Bob
    TODO: create deploy task token=abc123456789SECRET owner: Bob
    """
    tasks = extract_task_candidates(transcript)
    assert len(tasks) == 1
    assert tasks[0].sensitive is True
    assert "[REDACTED]" in tasks[0].summary
