"""Extract individual SendSprint screen mockups from GPT Image 2 storyboards.

The exported storyboard boards are the visual source of truth. This script keeps
the originals intact and writes one PNG per screen under ``telas/exports/screens``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image


ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
OUT_DIR = EXPORTS / "screens"


@dataclass(frozen=True)
class CropSpec:
    slug: str
    source: str
    box: tuple[int, int, int, int]
    surface: str
    title: str
    source_generator: str = "gpt-image-2"


def web_specs() -> list[CropSpec]:
    cols = [(0, 0, 512, 290), (512, 0, 1018, 290), (1018, 0, 1536, 290)]
    row2 = [(0, 290, 512, 540), (512, 290, 1018, 540), (1018, 290, 1536, 540)]
    row3 = [(0, 540, 512, 782), (512, 540, 1018, 782), (1018, 540, 1536, 782)]
    row4 = [(0, 782, 512, 1024), (512, 782, 1018, 1024), (1018, 782, 1536, 1024)]
    boxes = [*cols, *row2, *row3, *row4]
    items = [
        ("web-01-app-login", "App login"),
        ("web-02-empty-shell", "Empty shell"),
        ("web-03-provider-picker", "Provider picker"),
        ("web-04-azure-connect", "Azure connect"),
        ("web-05-jira-connect", "Jira connect"),
        ("web-06-import-progress", "Import progress"),
        ("web-07-kanban-backlog", "Kanban backlog"),
        ("web-08-card-detail-modal", "Card detail modal"),
        ("web-09-live-run", "Live run"),
        ("web-10-run-result", "Run result"),
        ("web-11-project-setup", "Project setup"),
        ("web-12-settings-connections", "Settings and connections"),
    ]
    return [
        CropSpec(slug, "web-master-storyboard.png", box, "web", title)
        for (slug, title), box in zip(items, boxes, strict=True)
    ]


def enterprise_specs() -> list[CropSpec]:
    boxes = [
        (0, 0, 768, 360),
        (768, 0, 1536, 360),
        (0, 360, 768, 650),
        (768, 360, 1536, 650),
        (0, 650, 768, 1024),
        (768, 650, 1536, 1024),
    ]
    items = [
        ("web-13-manager-console", "Manager console"),
        ("web-14-company-health", "Company health"),
        ("web-15-support-center", "Support center"),
        ("web-17-reports-analytics", "Reports analytics"),
        ("web-16-company-admin", "Company admin"),
        ("web-18-portfolio-view", "Portfolio view"),
    ]
    web = [
        CropSpec(slug, "enterprise-operations-storyboard.png", box, "web", title)
        for (slug, title), box in zip(items, boxes, strict=True)
    ]
    enterprise = [
        CropSpec(
            f"enterprise-{index:02d}-{slug.removeprefix('web-').split('-', 1)[1]}",
            "enterprise-operations-storyboard.png",
            box,
            "enterprise",
            title,
        )
        for index, ((slug, title), box) in enumerate(zip(items, boxes, strict=True), start=1)
    ]
    return [*web, *enterprise]


def desktop_specs() -> list[CropSpec]:
    return [
        CropSpec("desktop-win-01-login-shell", "desktop-master-storyboard.png", (185, 18, 488, 356), "desktop-windows", "Windows login shell"),
        CropSpec("desktop-win-02-empty-shell", "desktop-master-storyboard.png", (510, 18, 920, 356), "desktop-windows", "Windows empty shell"),
        CropSpec("desktop-win-03-backlog-kanban", "desktop-master-storyboard.png", (940, 18, 1530, 370), "desktop-windows", "Windows backlog kanban"),
        CropSpec("desktop-win-04-live-run", "desktop-master-storyboard.png", (198, 372, 812, 620), "desktop-windows", "Windows live run"),
        CropSpec("desktop-win-05-project-setup", "desktop-master-storyboard.png", (860, 372, 1400, 620), "desktop-windows", "Windows project setup"),
        CropSpec("desktop-mac-01-login-shell", "desktop-master-storyboard.png", (196, 662, 388, 970), "desktop-macos", "macOS login shell"),
        CropSpec("desktop-mac-02-empty-shell", "desktop-master-storyboard.png", (412, 662, 635, 970), "desktop-macos", "macOS empty shell"),
        CropSpec("desktop-mac-03-backlog-kanban", "desktop-master-storyboard.png", (636, 662, 920, 970), "desktop-macos", "macOS backlog kanban"),
        CropSpec("desktop-mac-04-live-run", "desktop-master-storyboard.png", (940, 662, 1184, 970), "desktop-macos", "macOS live run"),
        CropSpec("desktop-mac-05-manager-console", "desktop-master-storyboard.png", (1182, 662, 1518, 970), "desktop-macos", "macOS manager console"),
    ]


def mobile_console_specs() -> list[CropSpec]:
    mobile = [
        CropSpec("ios-01-login", "mobile-console-master-storyboard.png", (32, 138, 184, 488), "mobile-ios", "iOS login"),
        CropSpec("ios-02-home", "mobile-console-master-storyboard.png", (202, 138, 354, 488), "mobile-ios", "iOS home"),
        CropSpec("ios-03-backlog", "mobile-console-master-storyboard.png", (372, 138, 524, 488), "mobile-ios", "iOS backlog"),
        CropSpec("ios-04-task-detail", "mobile-console-master-storyboard.png", (542, 138, 694, 488), "mobile-ios", "iOS task detail"),
        CropSpec("ios-05-activity-feed", "mobile-console-master-storyboard.png", (712, 138, 868, 488), "mobile-ios", "iOS activity feed"),
        CropSpec("android-01-login", "mobile-console-master-storyboard.png", (32, 584, 176, 954), "mobile-android", "Android login"),
        CropSpec("android-02-home", "mobile-console-master-storyboard.png", (202, 584, 352, 954), "mobile-android", "Android home"),
        CropSpec("android-03-backlog", "mobile-console-master-storyboard.png", (372, 584, 522, 954), "mobile-android", "Android backlog"),
        CropSpec("android-04-task-detail", "mobile-console-master-storyboard.png", (542, 584, 692, 954), "mobile-android", "Android task detail"),
        CropSpec("android-05-manager-view", "mobile-console-master-storyboard.png", (714, 584, 866, 954), "mobile-android", "Android manager view"),
    ]
    console = [
        CropSpec("console-00-full-poster", "mobile-console-master-storyboard.png", (918, 24, 1514, 968), "console", "Console full poster"),
        CropSpec("console-01-login", "mobile-console-master-storyboard.png", (952, 110, 1116, 362), "console", "Console login"),
        CropSpec("console-02-provider-connect", "mobile-console-master-storyboard.png", (1126, 110, 1304, 362), "console", "Console provider connect"),
        CropSpec("console-03-import-summary", "mobile-console-master-storyboard.png", (1314, 110, 1492, 362), "console", "Console import summary"),
        CropSpec("console-04-live-narrative", "mobile-console-master-storyboard.png", (952, 374, 1116, 610), "console", "Console live narrative"),
        CropSpec("console-05-step-progress", "mobile-console-master-storyboard.png", (1126, 374, 1304, 610), "console", "Console step progress"),
        CropSpec("console-06-detailed-logs", "mobile-console-master-storyboard.png", (1314, 374, 1492, 610), "console", "Console detailed logs"),
        CropSpec("console-07-pull-request", "mobile-console-master-storyboard.png", (952, 622, 1116, 868), "console", "Console pull request"),
        CropSpec("console-08-human-review", "mobile-console-master-storyboard.png", (1126, 622, 1304, 868), "console", "Console human review"),
        CropSpec("console-09-deploy-handoff", "mobile-console-master-storyboard.png", (1314, 622, 1492, 868), "console", "Console deploy handoff"),
    ]
    return [*mobile, *console]


def all_specs() -> list[CropSpec]:
    return [*web_specs(), *enterprise_specs(), *desktop_specs(), *mobile_console_specs()]


def crop_all(specs: Iterable[CropSpec]) -> list[dict[str, object]]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    cache: dict[str, Image.Image] = {}

    for spec in specs:
        source = cache.get(spec.source)
        if source is None:
            source = Image.open(EXPORTS / spec.source).convert("RGB")
            cache[spec.source] = source

        target_dir = OUT_DIR / spec.surface
        target_dir.mkdir(parents=True, exist_ok=True)
        output = target_dir / f"{spec.slug}.png"
        source.crop(spec.box).save(output, optimize=True)

        record = asdict(spec)
        record["path"] = str(output.relative_to(ROOT)).replace("\\", "/")
        record["size"] = Image.open(output).size
        manifest.append(record)

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    generated = crop_all(all_specs())
    print(f"Generated {len(generated)} screen assets in {OUT_DIR}")
