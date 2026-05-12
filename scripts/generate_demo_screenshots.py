"""Generate mockup UI screenshots used as demo evidence by the SendSprint API.

Run once after install (or in CI) to refresh the bundled PNGs. Output goes to
`sendsprint/api/assets/screenshots/`. Uses Pillow only.

Each PNG looks like a credible test-evidence artifact: a login screen, a
dashboard, a passing/failing test report, a regression diff banner, and a
coverage summary. They are intentionally synthetic — no real product UI.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "sendsprint" / "api" / "assets" / "screenshots"
W, H = 1280, 800

PALETTE = {
    "bg": (7, 11, 26),
    "bg_deep": (3, 5, 13),
    "surface": (15, 21, 48),
    "surface_alt": (20, 29, 63),
    "border": (60, 75, 130),
    "text": (241, 244, 255),
    "muted": (154, 163, 199),
    "primary": (124, 92, 255),
    "primary_soft": (167, 139, 255),
    "accent": (34, 211, 238),
    "success": (52, 211, 153),
    "warning": (251, 191, 36),
    "danger": (248, 113, 113),
    "bar_dim": (35, 45, 80),
}


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for c in candidates:
        if Path(c).is_file():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _gradient_bg(img: Image.Image) -> None:
    px = img.load()
    for y in range(H):
        # vertical fade from bg_deep (top) to bg (bottom)
        t = y / H
        r = int(PALETTE["bg_deep"][0] * (1 - t) + PALETTE["bg"][0] * t)
        g = int(PALETTE["bg_deep"][1] * (1 - t) + PALETTE["bg"][1] * t)
        b = int(PALETTE["bg_deep"][2] * (1 - t) + PALETTE["bg"][2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)


def _rounded_rect(d: ImageDraw.ImageDraw, xy, radius=12, fill=None, outline=None, width=1):
    d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _topbar(d: ImageDraw.ImageDraw, title: str, accent_color):
    _rounded_rect(
        d, (24, 24, W - 24, 70), radius=14, fill=PALETTE["surface"], outline=PALETTE["border"]
    )
    # macos dots
    d.ellipse((42, 42, 60, 60), fill=(255, 95, 86))
    d.ellipse((68, 42, 86, 60), fill=(255, 189, 46))
    d.ellipse((94, 42, 112, 60), fill=(39, 201, 63))
    d.text((140, 38), title, font=_font(18), fill=PALETTE["muted"])
    d.text((W - 140, 38), "● live", font=_font(16, True), fill=accent_color)


def login_screen() -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg"])
    _gradient_bg(img)
    d = ImageDraw.Draw(img)
    _topbar(d, "SendSprint • E2E test — login flow", PALETTE["accent"])

    # Card center
    cx, cy = W // 2, H // 2 + 20
    cw, ch = 460, 460
    _rounded_rect(
        d,
        (cx - cw // 2, cy - ch // 2, cx + cw // 2, cy + ch // 2),
        radius=22,
        fill=PALETTE["surface"],
        outline=PALETTE["border"],
        width=1,
    )
    d.text((cx - 90, cy - 200), "⚡ SendSprint", font=_font(34, True), fill=PALETTE["text"])
    d.text((cx - 80, cy - 156), "Sign in to your team", font=_font(16), fill=PALETTE["muted"])

    # Email input
    d.text((cx - cw // 2 + 40, cy - 100), "EMAIL", font=_font(11), fill=PALETTE["muted"])
    _rounded_rect(
        d,
        (cx - cw // 2 + 40, cy - 80, cx + cw // 2 - 40, cy - 36),
        radius=10,
        fill=PALETTE["bg_deep"],
        outline=PALETTE["border"],
    )
    d.text((cx - cw // 2 + 56, cy - 70), "dev@sendsprint.ai", font=_font(16), fill=PALETTE["text"])

    # Password input
    d.text((cx - cw // 2 + 40, cy - 10), "PASSWORD", font=_font(11), fill=PALETTE["muted"])
    _rounded_rect(
        d,
        (cx - cw // 2 + 40, cy + 10, cx + cw // 2 - 40, cy + 54),
        radius=10,
        fill=PALETTE["bg_deep"],
        outline=PALETTE["border"],
    )
    d.text((cx - cw // 2 + 56, cy + 22), "•" * 14, font=_font(20), fill=PALETTE["text"])

    # Submit button (primary)
    _rounded_rect(
        d,
        (cx - cw // 2 + 40, cy + 80, cx + cw // 2 - 40, cy + 130),
        radius=12,
        fill=PALETTE["primary"],
    )
    d.text((cx - 32, cy + 96), "Sign in", font=_font(18, True), fill=(255, 255, 255))

    # Status
    d.text(
        (cx - 110, cy + 160), "✓ login captured at 03:12", font=_font(13), fill=PALETTE["success"]
    )
    return img


def dashboard_screen() -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg"])
    _gradient_bg(img)
    d = ImageDraw.Draw(img)
    _topbar(d, "SendSprint • dashboard render — post-login", PALETTE["primary_soft"])

    # Sidebar
    _rounded_rect(
        d, (24, 90, 250, H - 24), radius=14, fill=PALETTE["surface"], outline=PALETTE["border"]
    )
    items = ["📊 Overview", "📝 Sprints", "🛡️ Security", "📦 PRs", "⚙️ Settings"]
    for i, t in enumerate(items):
        y = 110 + i * 50
        if i == 0:
            _rounded_rect(d, (40, y, 234, y + 40), radius=8, fill=PALETTE["primary"])
            d.text((54, y + 12), t, font=_font(16, True), fill=(255, 255, 255))
        else:
            d.text((54, y + 12), t, font=_font(16), fill=PALETTE["muted"])

    # Main content — KPI cards
    kpis = [
        ("ACTIVE SPRINTS", "3", PALETTE["accent"]),
        ("ITEMS DONE", "47", PALETTE["success"]),
        ("OPEN PRs", "12", PALETTE["primary_soft"]),
        ("FAILING TESTS", "0", PALETTE["danger"]),
    ]
    for i, (lbl, val, col) in enumerate(kpis):
        x0 = 280 + (i % 4) * 240
        y0 = 110
        _rounded_rect(
            d,
            (x0, y0, x0 + 220, y0 + 110),
            radius=14,
            fill=PALETTE["surface"],
            outline=PALETTE["border"],
        )
        d.text((x0 + 16, y0 + 14), lbl, font=_font(11), fill=PALETTE["muted"])
        d.text((x0 + 16, y0 + 36), val, font=_font(40, True), fill=col)

    # Chart-ish bars
    _rounded_rect(
        d, (280, 240, W - 24, 480), radius=14, fill=PALETTE["surface"], outline=PALETTE["border"]
    )
    d.text((300, 256), "VELOCITY (last 7 days)", font=_font(12), fill=PALETTE["muted"])
    bars = [120, 80, 160, 110, 200, 90, 240]
    for i, h in enumerate(bars):
        x0 = 320 + i * 110
        y0 = 460 - h
        _rounded_rect(d, (x0, y0, x0 + 70, 460), radius=8, fill=PALETTE["primary"])
        d.text((x0 + 22, 470), f"D-{6 - i}", font=_font(11), fill=PALETTE["muted"])

    # Recent activity table
    _rounded_rect(
        d, (280, 500, W - 24, H - 24), radius=14, fill=PALETTE["surface"], outline=PALETTE["border"]
    )
    d.text((300, 514), "RECENT RUNS", font=_font(12), fill=PALETTE["muted"])
    rows = [
        ("PROJ-142", "feat: onboarding rework", "✓ delivered", PALETTE["success"]),
        ("PROJ-141", "fix: token refresh", "✓ delivered", PALETTE["success"]),
        ("PROJ-140", "test: regression suite", "↻ retrying", PALETTE["warning"]),
    ]
    for i, (k, t, s, col) in enumerate(rows):
        y = 545 + i * 40
        d.text((300, y), k, font=_font(13, True), fill=PALETTE["primary_soft"])
        d.text((400, y), t, font=_font(13), fill=PALETTE["text"])
        d.text((W - 200, y), s, font=_font(13, True), fill=col)
    return img


def test_report(passed: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg"])
    _gradient_bg(img)
    d = ImageDraw.Draw(img)
    title = "PASSED" if passed else "FAILED"
    color = PALETTE["success"] if passed else PALETTE["danger"]
    _topbar(d, f"pytest report — {title.lower()}", color)

    # Big banner
    _rounded_rect(
        d,
        (24, 90, W - 24, 220),
        radius=18,
        fill=(20, 50, 40) if passed else (60, 25, 30),
        outline=color,
        width=2,
    )
    d.text((52, 110), "✓" if passed else "✗", font=_font(72, True), fill=color)
    d.text(
        (140, 116),
        f"{'all tests passed' if passed else 'regression detected'}",
        font=_font(36, True),
        fill=PALETTE["text"],
    )
    if passed:
        d.text(
            (140, 168),
            "47 passed · 0 failed · 2 skipped · 12.4s",
            font=_font(18),
            fill=PALETTE["muted"],
        )
    else:
        d.text(
            (140, 168),
            "44 passed · 3 failed · 2 skipped · 14.1s",
            font=_font(18),
            fill=PALETTE["muted"],
        )

    # Test list
    rows = [
        ("test_login_flow.py::test_happy_path", True, "0.42s"),
        ("test_login_flow.py::test_invalid_password", True, "0.21s"),
        ("test_dashboard.py::test_kpis_render", passed, "0.88s"),
        ("test_dashboard.py::test_velocity_chart", passed, "0.61s"),
        ("test_regression.py::test_signup_email_validation", passed, "0.39s"),
        ("test_security.py::test_no_secrets_in_log", True, "0.18s"),
    ]
    y = 250
    for name, ok, dur in rows:
        bullet_color = PALETTE["success"] if ok else PALETTE["danger"]
        bullet = "✓" if ok else "✗"
        _rounded_rect(
            d,
            (24, y, W - 24, y + 50),
            radius=10,
            fill=PALETTE["surface"],
            outline=PALETTE["border"],
        )
        d.text((40, y + 14), bullet, font=_font(20, True), fill=bullet_color)
        d.text((76, y + 16), name, font=_font(15), fill=PALETTE["text"])
        d.text((W - 120, y + 16), dur, font=_font(15), fill=PALETTE["muted"])
        y += 60
    return img


def regression_diff() -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg"])
    _gradient_bg(img)
    d = ImageDraw.Draw(img)
    _topbar(d, "regression diff — login button color", PALETTE["warning"])

    half = (W - 60) // 2
    # Left: baseline
    _rounded_rect(
        d,
        (24, 100, 24 + half, H - 24),
        radius=14,
        fill=PALETTE["surface"],
        outline=PALETTE["border"],
    )
    d.text((48, 114), "BASELINE", font=_font(12), fill=PALETTE["muted"])
    _rounded_rect(d, (60, 200, 24 + half - 36, 280), radius=10, fill=PALETTE["primary"])
    d.text((24 + half // 2 - 36, 224), "Sign in", font=_font(18, True), fill=(255, 255, 255))
    d.text((48, 320), "primary: #7c5cff", font=_font(15), fill=PALETTE["text"])

    # Right: new
    _rounded_rect(
        d,
        (36 + half, 100, W - 24, H - 24),
        radius=14,
        fill=PALETTE["surface"],
        outline=PALETTE["border"],
    )
    d.text((60 + half, 114), "AFTER PATCH", font=_font(12), fill=PALETTE["muted"])
    _rounded_rect(d, (72 + half, 200, W - 60, 280), radius=10, fill=PALETTE["accent"])
    d.text(
        (36 + half + (W - 36 - half) // 2 - 60, 224),
        "Sign in",
        font=_font(18, True),
        fill=(0, 0, 0),
    )
    d.text((60 + half, 320), "primary: #22d3ee", font=_font(15), fill=PALETTE["text"])

    # Banner: regression flag
    _rounded_rect(
        d, (24, H - 90, W - 24, H - 50), radius=10, fill=(60, 25, 30), outline=PALETTE["danger"]
    )
    d.text(
        (48, H - 78),
        "✗ visual regression: brand color changed without ADR",
        font=_font(15, True),
        fill=PALETTE["danger"],
    )
    return img


def coverage_report() -> Image.Image:
    img = Image.new("RGB", (W, H), PALETTE["bg"])
    _gradient_bg(img)
    d = ImageDraw.Draw(img)
    _topbar(d, "coverage report — sendsprint/", PALETTE["success"])
    _rounded_rect(
        d, (24, 100, W - 24, H - 24), radius=14, fill=PALETTE["surface"], outline=PALETTE["border"]
    )

    d.text((48, 120), "TOTAL COVERAGE", font=_font(12), fill=PALETTE["muted"])
    d.text((48, 144), "92.4%", font=_font(64, True), fill=PALETTE["success"])

    files = [
        ("operators/jira_operator.py", 0.94),
        ("operators/azure_devops_operator.py", 0.91),
        ("flow/sprint_flow.py", 0.88),
        ("agents/lint_runner.py", 0.97),
        ("agents/test_runner.py", 0.93),
        ("agents/security_reviewer.py", 0.95),
        ("agents/pr_creator.py", 0.89),
    ]
    y = 250
    for name, cov in files:
        _rounded_rect(
            d,
            (40, y, W - 40, y + 50),
            radius=10,
            fill=PALETTE["surface_alt"],
            outline=PALETTE["border"],
        )
        d.text((60, y + 16), name, font=_font(15), fill=PALETTE["text"])
        # bar
        bx0, bx1 = W - 360, W - 140
        _rounded_rect(d, (bx0, y + 18, bx1, y + 32), radius=6, fill=PALETTE["bar_dim"])
        fill_x = bx0 + int((bx1 - bx0) * cov)
        col = PALETTE["success"] if cov >= 0.9 else PALETTE["warning"]
        _rounded_rect(d, (bx0, y + 18, fill_x, y + 32), radius=6, fill=col)
        d.text((W - 116, y + 16), f"{int(cov * 100)}%", font=_font(15, True), fill=col)
        y += 56
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    items = {
        "login.png": login_screen(),
        "dashboard.png": dashboard_screen(),
        "regression-fail.png": test_report(passed=False),
        "regression-pass.png": test_report(passed=True),
        "regression-diff.png": regression_diff(),
        "coverage.png": coverage_report(),
    }
    for name, img in items.items():
        out = OUT / name
        img.save(out, format="PNG", optimize=True)
        rel = out.relative_to(OUT.parent.parent.parent.parent)
        size_kb = out.stat().st_size // 1024
        print(f"  wrote {rel}: {size_kb} KB")


if __name__ == "__main__":
    main()
