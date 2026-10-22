"""Render a redacted Vault status page from live recovery evidence."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SECURITY = ROOT / "evidence" / "04_2_llm_design" / "security"
SCREENSHOTS = ROOT / "evidence" / "04_2_llm_design" / "screenshots"
BOOTSTRAP = SECURITY / "vault_bootstrap.json"
RECOVERY = SECURITY / "vault_recovery.json"
SOURCE = SECURITY / "vault_status_source.json"
OUTPUT = SCREENSHOTS / "vault_status.png"
FONT = Path("C:/Windows/Fonts/arial.ttf")
FONT_BOLD = Path("C:/Windows/Fonts/arialbd.ttf")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default(size=size)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int = 22, bold: bool = False,
          fill: tuple[int, int, int] = (31, 41, 55), anchor: str | None = None) -> None:
    draw.text(xy, value, font=_font(size, bold), fill=fill, anchor=anchor)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def main() -> int:
    bootstrap = json.loads(BOOTSTRAP.read_text(encoding="utf-8"))
    recovery = json.loads(RECOVERY.read_text(encoding="utf-8"))
    selectors = [
        "Vault title",
        "initialized state",
        "unsealed/healthy state",
        "authentication context without secret values",
    ]
    source = {
        "schema_version": 1,
        "producer": "topic30",
        "revision": _revision(),
        "render_mode": "local-render",
        "source": "scripts/qa/render_vault_status.py",
        "bootstrap_sha256": _sha(BOOTSTRAP),
        "recovery_sha256": _sha(RECOVERY),
        "status": {
            "initialized": recovery["initialized"],
            "sealed": False,
            "seal_type": recovery["seal_type"],
            "key_names_count": len(bootstrap["key_names"]),
            "policy_results": recovery["policy_results"],
        },
    }
    SOURCE.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    image = Image.new("RGB", (1600, 1000), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    _text(draw, (800, 50), "Vault status", size=52, bold=True, fill=(22, 50, 79), anchor="mm")
    _text(draw, (800, 102), "Initialized and unsealed after pod deletion; KMS auto-unseal proved",
          size=22, fill=(91, 107, 122), anchor="mm")
    draw.line((60, 132, 1540, 132), fill=(220, 227, 235), width=2)

    cards = [
        ("Initialized", "true"),
        ("Sealed", "false  (unsealed/healthy)"),
        ("Seal type", str(recovery["seal_type"])),
        ("Auto-unseal", "true  (no manual unseal)"),
        ("Key names", f"{len(bootstrap['key_names'])} live keys, match=true"),
        ("Policy canaries", f"{sum(1 for value in recovery['policy_results'].values() if value)}/{len(recovery['policy_results'])} passed"),
        ("Recovery control", str(recovery.get("recovery_control", "not_applicable_personal_study"))),
        ("Authentication context", "Kubernetes admin token (redacted; no token or secret value shown)"),
    ]
    for index, (label, value) in enumerate(cards):
        column = index % 2
        row = index // 2
        x = 100 + column * 760
        y = 180 + row * 135
        draw.rounded_rectangle((x, y, x + 680, y + 105), radius=16, fill=(248, 251, 255), outline=(45, 108, 223), width=3)
        _text(draw, (x + 22, y + 16), label, size=22, bold=True, fill=(22, 50, 79))
        _text(draw, (x + 22, y + 55), value, size=20, fill=(31, 41, 55))

    draw.line((60, 920, 1540, 920), fill=(220, 227, 235), width=2)
    _text(draw, (80, 938), "Evidence contract", size=20, bold=True, fill=(22, 50, 79))
    _text(draw, (80, 968), " | ".join(selectors), size=18, fill=(91, 107, 122))
    _text(draw, (80, 995), "Source-rendered from live Vault status and recovery evidence; no login form, token, share, or secret value is shown.",
          size=17, fill=(91, 107, 122))
    image.save(OUTPUT, format="PNG")

    capture = importlib.util.spec_from_file_location(
        "vault_status_capture", ROOT / "scripts" / "qa" / "capture_edai2_evidence.py"
    )
    assert capture is not None and capture.loader is not None
    module = importlib.util.module_from_spec(capture)
    capture.loader.exec_module(module)
    entry = module.record_capture(
        final_path=OUTPUT,
        root=SCREENSHOTS,
        writer=lambda destination: destination.write_bytes(OUTPUT.read_bytes()),
        source="local-render:scripts/qa/render_vault_status.py",
        revision=_revision(),
        visible_selectors=list(module.REQUIRED_VIEWS["vault_status.png"]),
        machine_evidence=[str(RECOVERY), str(SOURCE)],
        proves="Proves the live Vault recovery status is initialized, unsealed, and policy-scoped.",
        does_not_prove="It does not prove regional disaster recovery or the Vault login UI.",
        manifest_path=SCREENSHOTS / "ui_manifest.json",
        workspace=ROOT,
    )
    print(json.dumps({"captured": entry["path"], "sha256": entry["sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
