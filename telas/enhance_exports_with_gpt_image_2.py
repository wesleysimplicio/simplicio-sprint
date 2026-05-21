"""Batch-enhance exported image assets with GPT Image 2.

This utility walks ``telas/exports`` recursively, sends each supported image to
the OpenAI Images edit endpoint, and overwrites the original file only after a
backup copy is written. Use ``--dry-run`` first to inspect the plan.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = ROOT / "exports"
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
IGNORED_DIR_NAMES = {".gpt-image-2-backups", ".gpt-image-2-receipts"}
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_QUALITY = "high"
DEFAULT_BACKGROUND = "auto"
DEFAULT_SIZE = "auto"


@dataclass(frozen=True)
class ImageTask:
    source: Path
    relative_path: str
    width: int
    height: int
    output_format: str


@dataclass(frozen=True)
class Receipt:
    source: str
    backup: str
    model: str
    quality: str
    background: str
    size: str
    output_format: str
    processed_at: str


def discover_images(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(part in IGNORED_DIR_NAMES for part in path.parts)
    )


def output_format_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".jpg":
        return "jpeg"
    return suffix.lstrip(".")


def build_task(path: Path, root: Path) -> ImageTask:
    with Image.open(path) as image:
        width, height = image.size
    return ImageTask(
        source=path,
        relative_path=str(path.relative_to(root)).replace("\\", "/"),
        width=width,
        height=height,
        output_format=output_format_for(path),
    )


def build_edit_prompt(task: ImageTask) -> str:
    subject = "storyboard" if "storyboard" in task.source.name else "screen mockup"
    return (
        f"Improve the visual quality of this {subject} while preserving the exact composition, "
        f"aspect ratio, UI layout, copy, icons, colors, and product intent. Keep it as the same "
        f"SendSprint asset identified as {task.relative_path}. Increase sharpness, clarity, local "
        f"contrast, readability, texture fidelity, edge cleanliness, and overall polish. Remove "
        f"compression noise or blur artifacts, but do not redesign, crop, invent new elements, "
        f"change the framing, or alter the screen count."
    )


def ensure_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export the key or place it in a local .env "
            "file before running."
        )


def backup_path_for(source: Path, root: Path, backup_root: Path) -> Path:
    return backup_root / source.relative_to(root)


def decode_image_bytes(encoded: str) -> bytes:
    return base64.b64decode(encoded)


def write_receipts(receipts: Iterable[Receipt], receipt_path: Path) -> None:
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(receipt) for receipt in receipts]
    receipt_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def enhance_image(
    client: OpenAI,
    task: ImageTask,
    *,
    model: str,
    quality: str,
    background: str,
    size: str,
) -> bytes:
    with task.source.open("rb") as handle:
        result = client.images.edit(
            model=model,
            image=handle,
            prompt=build_edit_prompt(task),
            quality=quality,
            background=background,
            size=size,
            output_format=task.output_format,
        )
    return decode_image_bytes(result.data[0].b64_json)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Root folder to scan recursively for image assets.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="OpenAI image model to use. Defaults to gpt-image-2.",
    )
    parser.add_argument(
        "--quality",
        default=DEFAULT_QUALITY,
        choices=["auto", "low", "medium", "high"],
        help="Requested render quality for the edited images.",
    )
    parser.add_argument(
        "--background",
        default=DEFAULT_BACKGROUND,
        choices=["auto", "opaque", "transparent"],
        help="Background policy supported by GPT Image models.",
    )
    parser.add_argument(
        "--size",
        default=DEFAULT_SIZE,
        help="Output size. Use auto to preserve model choice or pass explicit WxH.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the files that would be processed without calling the API.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    input_dir = args.input_dir.resolve()
    images = discover_images(input_dir)
    tasks = [build_task(path, input_dir) for path in images]

    if args.dry_run:
        for task in tasks:
            print(
                f"DRY-RUN {task.relative_path} "
                f"{task.width}x{task.height} -> {task.output_format}"
            )
        print(f"Planned {len(tasks)} image edits in {input_dir}")
        return 0

    ensure_api_key()
    client = OpenAI()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_root = input_dir / ".gpt-image-2-backups" / stamp
    receipt_path = input_dir / ".gpt-image-2-receipts" / f"{stamp}.json"
    receipts: list[Receipt] = []

    for task in tasks:
        backup_path = backup_path_for(task.source, input_dir, backup_root)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(task.source, backup_path)

        enhanced = enhance_image(
            client,
            task,
            model=args.model,
            quality=args.quality,
            background=args.background,
            size=args.size,
        )
        task.source.write_bytes(enhanced)

        receipt = Receipt(
            source=task.relative_path,
            backup=str(backup_path.relative_to(input_dir)).replace("\\", "/"),
            model=args.model,
            quality=args.quality,
            background=args.background,
            size=args.size,
            output_format=task.output_format,
            processed_at=datetime.now(UTC).isoformat(),
        )
        receipts.append(receipt)
        print(f"UPDATED {task.relative_path}")

    write_receipts(receipts, receipt_path)
    receipt_rel = receipt_path.relative_to(input_dir)
    print(f"Updated {len(receipts)} images. Receipts written to {receipt_rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
