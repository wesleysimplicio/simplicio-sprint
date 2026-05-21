from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "telas" / "enhance_exports_with_gpt_image_2.py"
)
SPEC = importlib.util.spec_from_file_location("enhance_exports_with_gpt_image_2", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_discover_images_recurses_and_skips_internal_dirs(tmp_path: Path):
    root = tmp_path / "exports"
    nested = root / "screens" / "web"
    nested.mkdir(parents=True)
    (root / ".gpt-image-2-backups" / "20260521T000000Z").mkdir(parents=True)
    Image.new("RGB", (10, 10), "white").save(root / "board.png")
    Image.new("RGB", (10, 10), "white").save(nested / "screen.webp")
    Image.new("RGB", (10, 10), "white").save(
        root / ".gpt-image-2-backups" / "20260521T000000Z" / "old.png"
    )
    (root / "notes.txt").write_text("ignore", encoding="utf-8")

    discovered = MODULE.discover_images(root)

    assert [path.relative_to(root).as_posix() for path in discovered] == [
        "board.png",
        "screens/web/screen.webp",
    ]


def test_build_task_reads_dimensions_and_format(tmp_path: Path):
    root = tmp_path / "exports"
    root.mkdir()
    image_path = root / "sample.jpg"
    Image.new("RGB", (320, 180), "white").save(image_path)

    task = MODULE.build_task(image_path, root)

    assert task.relative_path == "sample.jpg"
    assert task.width == 320
    assert task.height == 180
    assert task.output_format == "jpeg"


def test_build_edit_prompt_preserves_layout_language(tmp_path: Path):
    root = tmp_path / "exports"
    root.mkdir()
    image_path = root / "desktop-master-storyboard.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    task = MODULE.build_task(image_path, root)

    prompt = MODULE.build_edit_prompt(task)

    assert "preserving the exact composition" in prompt
    assert "desktop-master-storyboard.png" in prompt
    assert "do not redesign" in prompt
