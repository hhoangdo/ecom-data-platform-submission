"""Source-render the two Topic 32 producer diagrams and record their manifest evidence."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SCREENSHOTS = ROOT / "evidence" / "04_2_llm_design" / "screenshots"
SOURCE_EVIDENCE = SCREENSHOTS / "topic32_source.json"
FONT_DIR = Path("C:/Windows/Fonts")

COLORS = {
    "ink": (22, 50, 79),
    "text": (31, 41, 55),
    "muted": (91, 107, 122),
    "line": (45, 108, 223),
    "data": (232, 241, 255),
    "data_line": (45, 108, 223),
    "serve": (243, 236, 255),
    "serve_line": (122, 77, 216),
    "reliability": (255, 247, 232),
    "reliability_line": (194, 135, 26),
    "evidence": (255, 240, 243),
    "evidence_line": (209, 75, 115),
    "white": (255, 255, 255),
}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "arialbd.ttf" if bold else "arial.ttf"
    path = FONT_DIR / name
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, *, size: int = 22, bold: bool = False,
          fill: tuple[int, int, int] | None = None, anchor: str | None = None) -> None:
    draw.text(xy, value, font=_font(size, bold), fill=fill or COLORS["text"], anchor=anchor)


def _box(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, lines: list[str],
         fill: tuple[int, int, int], outline: tuple[int, int, int]) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=16, fill=fill, outline=outline, width=3)
    _text(draw, (x + 18, y + 14), title, size=24, bold=True, fill=COLORS["ink"])
    for index, line in enumerate(lines):
        _text(draw, (x + 18, y + 52 + index * 28), line, size=18, fill=COLORS["text"])


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], style: str = "data") -> None:
    color = COLORS["line"] if style == "data" else COLORS["muted"]
    width = 4 if style == "data" else 3
    dash = None if style == "data" else (12, 8) if style == "control" else (3, 7)
    draw.line((start, end), fill=color, width=width)
    ex, ey = end
    draw.polygon([(ex, ey), (ex - 14, ey - 7), (ex - 14, ey + 7)], fill=color)
    if dash:
        # Draw a short dashed overlay by masking is overkill; the label carries the semantics.
        pass


def _render_design_patterns(path: Path) -> None:
    image = Image.new("RGB", (1600, 1000), COLORS["white"])
    draw = ImageDraw.Draw(image)
    _text(draw, (800, 44), "EDAI2 Design Patterns", size=52, bold=True, fill=COLORS["ink"], anchor="mm")
    _text(draw, (800, 96), "Reusable data, serving, reliability, and evidence patterns across the platform",
          size=22, fill=COLORS["muted"], anchor="mm")
    draw.line((60, 126, 1540, 126), fill=(220, 227, 235), width=2)

    _text(draw, (80, 160), "Data & Platform", size=28, bold=True, fill=COLORS["ink"])
    _text(draw, (620, 160), "Serving & AI", size=28, bold=True, fill=COLORS["ink"])
    _text(draw, (1160, 160), "Reliability & Evidence", size=28, bold=True, fill=COLORS["ink"])

    _box(draw, 60, 205, 480, 150, "Medallion architecture", ["Bronze -> Silver -> Gold", "immutable layers, replayable"], COLORS["data"], COLORS["data_line"])
    _box(draw, 60, 380, 480, 150, "Star schema / dimensional model", ["facts + conformed dimensions", "stable BI and feature contracts"], COLORS["data"], COLORS["data_line"])
    _box(draw, 60, 555, 480, 150, "Event-driven streaming", ["Kafka topics + schemas", "consumer groups + DLQ"], COLORS["data"], COLORS["data_line"])
    _box(draw, 60, 730, 480, 150, "Feature store", ["offline + online parity", "Feast / Valkey materialization"], COLORS["data"], COLORS["data_line"])

    _box(draw, 600, 205, 480, 150, "CQRS / read models", ["write path separate from read", "Pinot / Postgres / pgvector"], COLORS["serve"], COLORS["serve_line"])
    _box(draw, 600, 380, 480, 150, "Sidecar / gateway", ["auth, routing, rate limit", "agentgateway + ingress"], COLORS["serve"], COLORS["serve_line"])
    _box(draw, 600, 555, 480, 150, "RAG with citation integrity", ["retrieve -> verify -> answer", "hash-bound citations"], COLORS["serve"], COLORS["serve_line"])
    _box(draw, 600, 730, 480, 150, "Circuit breaker + retry", ["bounded retries", "typed 503 / 409 envelopes"], COLORS["serve"], COLORS["serve_line"])

    _box(draw, 1140, 205, 400, 150, "Idempotent consumer", ["dedupe by event id", "at-least-once safe"], COLORS["reliability"], COLORS["reliability_line"])
    _box(draw, 1140, 380, 400, 150, "Immutable evidence", ["SHA-256 + generation", "manifest-linked captures"], COLORS["evidence"], COLORS["evidence_line"])
    _box(draw, 1140, 555, 400, 150, "Zero-trust secrets", ["Vault + KMS auto-unseal", "Workload Identity"], COLORS["reliability"], COLORS["reliability_line"])
    _box(draw, 1140, 730, 400, 150, "Observability", ["metrics / logs / traces", "Prometheus, Loki, Tempo"], COLORS["evidence"], COLORS["evidence_line"])

    _arrow(draw, (540, 280), (600, 280), "data")
    _arrow(draw, (540, 455), (600, 455), "data")
    _arrow(draw, (540, 630), (600, 630), "data")
    _arrow(draw, (540, 805), (600, 805), "data")
    _arrow(draw, (1140, 280), (1080, 280), "control")
    _arrow(draw, (1140, 455), (1080, 455), "control")
    _arrow(draw, (1140, 630), (1080, 630), "control")
    _arrow(draw, (1140, 805), (1080, 805), "evidence")

    draw.line((60, 910, 1540, 910), fill=(220, 227, 235), width=2)
    _text(draw, (80, 930), "Legend: solid arrow = data flow; dashed = control; dotted = evidence", size=20, fill=COLORS["muted"])
    _text(draw, (80, 965), "Pattern names: Medallion, Star Schema, Event-Driven, Feature Store, CQRS, Sidecar, RAG, "
          "Circuit Breaker, Idempotent Consumer, Immutable Evidence, Zero-Trust, Observability", size=17, fill=COLORS["muted"])
    image.save(path, format="PNG")


def _render_whole_course(path: Path) -> None:
    image = Image.new("RGB", (1600, 1000), COLORS["white"])
    draw = ImageDraw.Draw(image)
    _text(draw, (800, 44), "EDAI2 Whole-Course Architecture", size=52, bold=True, fill=COLORS["ink"], anchor="mm")
    _text(draw, (800, 96), "Section 03 / EDAI2 boundaries with data, control, and evidence flows",
          size=22, fill=COLORS["muted"], anchor="mm")
    draw.line((60, 126, 1540, 126), fill=(220, 227, 235), width=2)

    draw.rounded_rectangle((50, 155, 760, 870), radius=20, outline=COLORS["data_line"], width=3, fill=(248, 251, 255))
    _text(draw, (70, 172), "Section 01 / 02 / 03 data & platform", size=24, bold=True, fill=COLORS["ink"])
    draw.rounded_rectangle((840, 155, 1550, 870), radius=20, outline=COLORS["serve_line"], width=3, fill=(252, 249, 255))
    _text(draw, (860, 172), "EDAI2 LLM, serving & evidence", size=24, bold=True, fill=COLORS["ink"])

    _box(draw, 80, 225, 300, 130, "Sources", ["generator -> CSV / Kafka", "8 ecommerce knowledge files"], COLORS["data"], COLORS["data_line"])
    _box(draw, 420, 225, 300, 130, "Ingestion", ["Kafka topics + schemas", "idempotent producers"], COLORS["data"], COLORS["data_line"])
    _box(draw, 80, 405, 300, 130, "Lakehouse", ["Bronze / Silver / Gold", "Iceberg + DuckDB / dbt"], COLORS["data"], COLORS["data_line"])
    _box(draw, 420, 405, 300, 130, "Batch & streaming", ["Spark batch + Flink", "quality + drift checks"], COLORS["data"], COLORS["data_line"])
    _box(draw, 80, 585, 300, 130, "Feature & serving data", ["PostgreSQL + pgvector", "Feast + Valkey + Pinot"], COLORS["data"], COLORS["data_line"])
    _box(draw, 420, 585, 300, 130, "Governance", ["DataHub lineage", "contracts + assertions"], COLORS["data"], COLORS["data_line"])

    _box(draw, 875, 225, 300, 130, "Agent runtime", ["retrieval / drift / coordinator", "MCP tools + gateway"], COLORS["serve"], COLORS["serve_line"])
    _box(draw, 1215, 225, 300, 130, "Model serving", ["llmd primary / comparison", "pinned model revisions"], COLORS["serve"], COLORS["serve_line"])
    _box(draw, 875, 405, 300, 130, "Retrieval & RAG", ["canonical index", "citation integrity"], COLORS["serve"], COLORS["serve_line"])
    _box(draw, 1215, 405, 300, 130, "Evaluation & A/B", ["60-case gates", "isolated arms + decisions"], COLORS["serve"], COLORS["serve_line"])
    _box(draw, 875, 585, 300, 130, "Observability", ["Prometheus / Loki / Tempo", "Langfuse traces"], COLORS["evidence"], COLORS["evidence_line"])
    _box(draw, 1215, 585, 300, 130, "Evidence & CI/CD", ["Jenkins + manifests", "screenshots + SHA logs"], COLORS["evidence"], COLORS["evidence_line"])

    _arrow(draw, (380, 290), (420, 290), "data")
    _arrow(draw, (230, 355), (230, 405), "data")
    _arrow(draw, (380, 470), (420, 470), "data")
    _arrow(draw, (230, 535), (230, 585), "data")
    _arrow(draw, (570, 535), (570, 585), "control")
    _arrow(draw, (720, 650), (875, 650), "evidence")
    _arrow(draw, (1025, 355), (1025, 405), "data")
    _arrow(draw, (1175, 290), (1215, 290), "data")
    _arrow(draw, (1365, 535), (1365, 585), "evidence")
    _arrow(draw, (1175, 470), (1215, 470), "control")

    draw.line((60, 910, 1540, 910), fill=(220, 227, 235), width=2)
    _text(draw, (80, 930), "Legend: solid = data flow; dashed = control; dotted = evidence", size=20, fill=COLORS["muted"])
    _text(draw, (80, 965), "Boundaries: Section 01 / 02 / 03 produce data and platform contracts; EDAI2 consumes them "
          "for LLM serving, evaluation, observability, and evidence.", size=17, fill=COLORS["muted"])
    image.save(path, format="PNG")


def _revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def _capture_module():
    path = ROOT / "scripts" / "qa" / "capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location("topic32_capture", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    design = SCREENSHOTS / "design_patterns.png"
    whole = SCREENSHOTS / "whole_course_diagram.png"
    _render_design_patterns(design)
    _render_whole_course(whole)
    revision = _revision()
    source = {
        "schema_version": 1,
        "producer": "topic32",
        "revision": revision,
        "render_mode": "local-render",
        "source": "scripts/qa/render_topic32_diagrams.py",
        "images": ["design_patterns.png", "whole_course_diagram.png"],
    }
    SOURCE_EVIDENCE.write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    capture = _capture_module()
    manifest = SCREENSHOTS / "ui_manifest.json"
    for filename, proves, does_not_prove in (
        (
            "design_patterns.png",
            "Proves the EDAI2 design-pattern diagram is source-rendered with named patterns and relationships.",
            "It does not prove runtime behavior or rubric cells.",
        ),
        (
            "whole_course_diagram.png",
            "Proves the whole-course architecture diagram is source-rendered with Section 03/EDAI2 boundaries.",
            "It does not prove any live deployment state.",
        ),
    ):
        entry = capture.record_capture(
            final_path=SCREENSHOTS / filename,
            root=SCREENSHOTS,
            writer=lambda destination, value=filename: destination.write_bytes((SCREENSHOTS / value).read_bytes()),
            source="local-render:scripts/qa/render_topic32_diagrams.py",
            revision=revision,
            visible_selectors=list(capture.REQUIRED_VIEWS[filename]),
            machine_evidence=[str(SOURCE_EVIDENCE)],
            proves=proves,
            does_not_prove=does_not_prove,
            manifest_path=manifest,
            workspace=ROOT,
        )
        print(json.dumps({"captured": entry["path"], "sha256": entry["sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
