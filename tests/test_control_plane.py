"""Tests for multi-agent control plane."""

from __future__ import annotations

import pytest

from sendsprint.control_plane import ControlPlaneState, WorkerAssignment


def test_control_plane_rejects_duplicate_ownership() -> None:
    assignment = WorkerAssignment(
        worker_id="a",
        issue_key="#1",
        repo="repo",
        branch="feature/1",
        worktree_path="/tmp/repo-wt-1",
    )
    state = ControlPlaneState().claim(assignment)
    with pytest.raises(ValueError):
        state.claim(assignment.model_copy(update={"worker_id": "b", "worktree_path": "/tmp/x"}))


def test_control_plane_updates_status() -> None:
    assignment = WorkerAssignment(
        worker_id="a",
        issue_key="#1",
        repo="repo",
        branch="feature/1",
        worktree_path="/tmp/repo-wt-1",
    )
    state = ControlPlaneState().claim(assignment).update("a", "done")
    assert state.active() == []
