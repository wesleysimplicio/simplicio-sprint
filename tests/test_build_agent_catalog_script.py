from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_agent_catalog.py"
    spec = importlib.util.spec_from_file_location("build_agent_catalog_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_catalog_builder_handles_hash_collision() -> None:
    mod = _load_script()
    root = mod.Node()
    first = mod.Leaf(key="agent.one.plan", hash=7, tuple={"yool_id": "agent.one.plan"})
    second = mod.Leaf(key="agent.two.plan", hash=7, tuple={"yool_id": "agent.two.plan"})

    mod.insert(root, first, level=mod.MAX_LEVELS)
    mod.insert(root, second, level=mod.MAX_LEVELS)

    payload = mod.trie_to_json(root)
    collision = next(iter(payload["children"].values()))
    assert collision["kind"] == "collision"
    assert {leaf["key"] for leaf in collision["leaves"]} == {
        "agent.one.plan",
        "agent.two.plan",
    }


def test_catalog_builder_check_mode_detects_drift(tmp_path: Path) -> None:
    mod = _load_script()
    output = tmp_path / ".catalog" / "agents.json"

    assert mod.main(["--output", str(output)]) == 0
    assert mod.main(["--output", str(output), "--check"]) == 0

    output.write_text("{}", encoding="utf-8")
    assert mod.main(["--output", str(output), "--check"]) == 1
