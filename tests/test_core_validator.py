"""Tests for the sendsprint.core validator (Rust + Python fallback)."""

from __future__ import annotations

import json
import os

import pytest

from sendsprint import core


def _base_sprint(items: list[dict]) -> dict:
    return {"id": "S-1", "name": "Test Sprint", "items": items}


def _item(**overrides) -> dict:
    base = {
        "id": "1",
        "key": "K-1",
        "type": "Task",
        "title": "t",
        "status": "todo",
        "labels": [],
        "links": [],
        "comments": [],
        "attachments": [],
    }
    base.update(overrides)
    return base


@pytest.fixture(params=["python", "rust"])
def backend(request, monkeypatch):
    if request.param == "rust" and not core.RUST_AVAILABLE:
        pytest.skip("sendsprint_core wheel not installed")
    if request.param == "python":
        monkeypatch.setenv("SENDSPRINT_USE_RUST_CORE", "0")
    else:
        monkeypatch.setenv("SENDSPRINT_USE_RUST_CORE", "1")
    return request.param


def test_clean_sprint_is_ok(backend):
    sprint = _base_sprint(
        [
            _item(key="A-1"),
            _item(key="A-2", parent_key="A-1"),
        ]
    )
    report = core.validate_sprint_plan(sprint)
    assert report["backend"] == backend
    assert report["ok"] is True
    assert report["error_count"] == 0
    assert report["item_count"] == 2


def test_duplicate_key_is_error(backend):
    sprint = _base_sprint(
        [
            _item(key="A-1"),
            _item(key="A-1", id="2"),
        ]
    )
    report = core.validate_sprint_plan(sprint)
    assert report["ok"] is False
    codes = [f["code"] for f in report["findings"]]
    assert "duplicate_key" in codes


def test_self_parent_is_error(backend):
    sprint = _base_sprint([_item(key="A-1", parent_key="A-1")])
    report = core.validate_sprint_plan(sprint)
    assert report["ok"] is False
    codes = [f["code"] for f in report["findings"]]
    assert "self_parent" in codes


def test_parent_cycle_is_error(backend):
    sprint = _base_sprint(
        [
            _item(key="A-1", parent_key="A-3"),
            _item(key="A-2", parent_key="A-1"),
            _item(key="A-3", parent_key="A-2"),
        ]
    )
    report = core.validate_sprint_plan(sprint)
    assert report["ok"] is False
    cycle_findings = [f for f in report["findings"] if f["code"] == "parent_cycle"]
    assert len(cycle_findings) >= 1


def test_orphan_parent_is_warning(backend):
    sprint = _base_sprint([_item(key="A-1", parent_key="GHOST")])
    report = core.validate_sprint_plan(sprint)
    assert report["ok"] is True  # warnings don't fail
    codes = [f["code"] for f in report["findings"]]
    assert "orphan_parent" in codes
    assert report["warning_count"] >= 1


def test_invalid_story_points_is_error(backend):
    sprint = _base_sprint([_item(key="A-1", story_points=-3)])
    report = core.validate_sprint_plan(sprint)
    assert report["ok"] is False
    codes = [f["code"] for f in report["findings"]]
    assert "invalid_story_points" in codes


def test_unknown_status_is_warning(backend):
    sprint = _base_sprint([_item(key="A-1", status="quantum")])
    report = core.validate_sprint_plan(sprint)
    assert report["ok"] is True
    codes = [f["code"] for f in report["findings"]]
    assert "unknown_status" in codes


def test_story_without_acceptance_criteria_warns(backend):
    sprint = _base_sprint([_item(key="S-1", type="Story", acceptance_criteria="")])
    report = core.validate_sprint_plan(sprint)
    codes = [f["code"] for f in report["findings"]]
    assert "missing_acceptance_criteria" in codes


def test_story_with_acceptance_criteria_passes(backend):
    sprint = _base_sprint(
        [_item(key="S-1", type="Story", acceptance_criteria="- must do X")]
    )
    report = core.validate_sprint_plan(sprint)
    codes = [f["code"] for f in report["findings"]]
    assert "missing_acceptance_criteria" not in codes


def test_duplicate_label_is_info(backend):
    sprint = _base_sprint([_item(key="A-1", labels=["x", "x", "y"])])
    report = core.validate_sprint_plan(sprint)
    codes = [f["code"] for f in report["findings"]]
    assert "duplicate_label" in codes
    assert report["info_count"] >= 1


def test_external_link_is_info(backend):
    sprint = _base_sprint(
        [_item(key="A-1", links=[{"type": "blocks", "target_key": "OTHER-99"}])]
    )
    report = core.validate_sprint_plan(sprint)
    codes = [f["code"] for f in report["findings"]]
    assert "external_link" in codes


def test_accepts_bytes(backend):
    sprint = _base_sprint([_item(key="A-1")])
    payload = json.dumps(sprint).encode("utf-8")
    report = core.validate_sprint_plan(payload)
    assert report["ok"] is True
    assert report["item_count"] == 1


def test_accepts_str(backend):
    sprint = _base_sprint([_item(key="A-1")])
    report = core.validate_sprint_plan(json.dumps(sprint))
    assert report["ok"] is True


def test_python_and_rust_agree_on_complex_sprint():
    if not core.RUST_AVAILABLE:
        pytest.skip("sendsprint_core wheel not installed")

    sprint = _base_sprint(
        [
            _item(key="A-1"),
            _item(key="A-2", parent_key="A-1"),
            _item(key="A-3", parent_key="GHOST"),
            _item(key="A-4", type="Story", acceptance_criteria=""),
            _item(key="A-5", status="ufo"),
            _item(key="A-6", labels=["x", "x"]),
            _item(key="A-7", parent_key="A-9"),
            _item(key="A-8", parent_key="A-7"),
            _item(key="A-9", parent_key="A-8"),
        ]
    )

    os.environ["SENDSPRINT_USE_RUST_CORE"] = "0"
    py_report = core.validate_sprint_plan(sprint)
    os.environ["SENDSPRINT_USE_RUST_CORE"] = "1"
    rs_report = core.validate_sprint_plan(sprint)

    assert py_report["error_count"] == rs_report["error_count"]
    assert py_report["warning_count"] == rs_report["warning_count"]
    assert py_report["info_count"] == rs_report["info_count"]
    py_codes = sorted(f["code"] for f in py_report["findings"])
    rs_codes = sorted(f["code"] for f in rs_report["findings"])
    assert py_codes == rs_codes


def test_invalid_json_bytes_raises():
    if not core.RUST_AVAILABLE:
        pytest.skip("sendsprint_core wheel not installed")
    os.environ["SENDSPRINT_USE_RUST_CORE"] = "1"
    with pytest.raises(ValueError):
        core.validate_sprint_plan(b"{not json")


def test_backend_reflects_env(monkeypatch):
    monkeypatch.setenv("SENDSPRINT_USE_RUST_CORE", "0")
    assert core.backend() == "python"
    if core.RUST_AVAILABLE:
        monkeypatch.setenv("SENDSPRINT_USE_RUST_CORE", "1")
        assert core.backend() == "rust"
