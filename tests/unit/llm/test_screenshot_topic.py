from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
REVISION = "a" * 40


def _load_script():
    path = ROOT / "scripts/qa/capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _writer(seed: int):
    def write(destination: Path) -> None:
        image = Image.new("RGB", (1600, 1000), (10 + seed, 20, 30))
        ImageDraw.Draw(image).rectangle([0, 0, 100 + seed, 100 + seed], fill=(200, 100, 50))
        image.save(destination, format="PNG")

    return write


def _machine(tmp_path: Path, name: str) -> str:
    path = tmp_path / name
    path.write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    return str(path)


def _record(capture, root: Path, filename: str, machine: str, seed: int) -> None:
    capture.record_capture(
        final_path=root / filename, root=root, writer=_writer(seed),
        source="https://example.test/" + filename, revision=REVISION,
        visible_selectors=list(capture.REQUIRED_VIEWS[filename]),
        machine_evidence=[machine], proves="Proves the view is contextual.",
        does_not_prove="It does not prove unrelated gates.",
        manifest_path=root / "ui_manifest.json", workspace=root,
    )


def test_screenshot_topic_passes_on_exact_owned_set() -> None:
    """A complete Topic 28 manifest must verify with its exact count."""
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _record(capture, root, "airflow_rag_graph.png", _machine(root, "a.json"), 1)
        _record(capture, root, "datahub_rag_lineage.png", _machine(root, "b.json"), 2)
        result = capture.verify_screenshot_topic(
            root / "ui_manifest.json", root, 28, 2, revision=REVISION, workspace=root
        )
        assert result["topic"] == 28 and result["count"] == 2


def test_screenshot_topic_rejects_unknown_topic(tmp_path: Path) -> None:
    capture = _load_script()
    with pytest.raises(ValueError, match="screenshot topic"):
        capture.verify_screenshot_topic(
            tmp_path / "missing.json", tmp_path, 99, 0, revision=REVISION, workspace=tmp_path
        )


def test_screenshot_topic_rejects_count_mismatch() -> None:
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _record(capture, root, "airflow_rag_graph.png", _machine(root, "a.json"), 1)
        _record(capture, root, "datahub_rag_lineage.png", _machine(root, "b.json"), 2)
        with pytest.raises(ValueError, match="count"):
            capture.verify_screenshot_topic(
                root / "ui_manifest.json", root, 28, 3, revision=REVISION, workspace=root
            )


def test_screenshot_topic_rejects_missing_owned_entry() -> None:
    capture = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _record(capture, root, "grafana_http.png", _machine(root, "a.json"), 1)
        _record(capture, root, "grafana_compute.png", _machine(root, "b.json"), 2)
        with pytest.raises(ValueError, match="missing"):
            capture.verify_screenshot_topic(
                root / "ui_manifest.json", root, 27, 2, revision=REVISION, workspace=root
            )


def test_topic_27_owns_exactly_sixteen_named_screenshots() -> None:
    """Topic 27 owns ten gateway/telemetry views plus six Jenkins pages, no more."""
    capture = _load_script()
    owned = set(capture.TOPIC_SCREENSHOT_SETS[27])
    assert len(owned) == 16
    assert {name for name in owned if name.startswith("jenkins_")} == {
        "jenkins_rag_index.png", "jenkins_retrieval_agent.png", "jenkins_drift_agent.png",
        "jenkins_coordinator.png", "jenkins_feast_offline.png", "jenkins_feast_online.png",
    }
    assert "grafana_ab.png" in owned


def _section03_png(destination: Path, width: int = 1600, height: int = 900, seed: int = 3) -> None:
    image = Image.new("RGB", (width, height), (10 + seed, 20, 30))
    ImageDraw.Draw(image).rectangle([0, 0, 100 + seed, 100 + seed], fill=(200, 100, 50))
    image.save(destination, format="PNG")


def test_verify_screenshots_only_flags_parse() -> None:
    """T31 Task 1 audit flags must parse (no argparse exit 2)."""
    capture = _load_script()
    args = capture.build_parser().parse_args([
        "--verify-screenshots-only",
        "--expected-edai2-count", "32",
        "--expected-extra", "gcp_billing_spend.png",
        "--ui-dimensions", "1600x1000",
        "--section03-dimensions", "1600x900",
        "--manifest", "evidence/04_2_llm_design/screenshots/ui_manifest.json",
        "--section03-manifest", "evidence/03_data_generator_improvement/section03_manifest.json",
        "--output", "tmp/edai2-gcp/topic31-screenshot-audit.json",
        "--strict-partial",
    ])
    assert args.verify_screenshots_only is True
    assert args.expected_edai2_count == 32
    assert args.ui_dimensions == "1600x1000"
    assert args.section03_dimensions == "1600x900"
    assert args.strict_partial is True


def test_verify_screenshots_only_is_read_only(tmp_path: Path) -> None:
    """Audit must never write/replace PNGs or manifests (two runs, zero mtimes)."""
    capture = _load_script()
    root = tmp_path / "shots"
    root.mkdir()
    _record(capture, root, "airflow_rag_graph.png", _machine(root, "a.json"), 1)
    before_png = (root / "airflow_rag_graph.png").stat().st_mtime_ns
    before_manifest = (root / "ui_manifest.json").stat().st_mtime_ns
    audit_path = tmp_path / "audit.json"
    first = capture.verify_screenshots_only(
        root=root, manifest=root / "ui_manifest.json", section03_manifest=None,
        expected_edai2_count=32, expected_extra=["gcp_billing_spend.png"],
        ui_dimensions=(1600, 1000), section03_dimensions=(1600, 900),
        output=audit_path, strict_partial=True,
        allow_pending_producer_topic=None, workspace=root,
    )
    second = capture.verify_screenshots_only(
        root=root, manifest=root / "ui_manifest.json", section03_manifest=None,
        expected_edai2_count=32, expected_extra=["gcp_billing_spend.png"],
        ui_dimensions=(1600, 1000), section03_dimensions=(1600, 900),
        output=tmp_path / "audit2.json", strict_partial=True,
        allow_pending_producer_topic=None, workspace=root,
    )
    assert (root / "airflow_rag_graph.png").stat().st_mtime_ns == before_png
    assert (root / "ui_manifest.json").stat().st_mtime_ns == before_manifest
    assert first == second or first["files"] == second["files"]
    by_name = {item["name"]: item for item in first["files"]}
    assert by_name["airflow_rag_graph.png"]["status"] == "Pass"


def test_strict_partial_scopes_pending_to_topic32_only(tmp_path: Path) -> None:
    """Only design_patterns + whole_course_diagram may be PendingProducer."""
    capture = _load_script()
    root = tmp_path / "empty"
    root.mkdir()
    (root / "ui_manifest.json").write_text("[]\n", encoding="utf-8")
    strict = capture.verify_screenshots_only(
        root=root, manifest=root / "ui_manifest.json", section03_manifest=None,
        expected_edai2_count=32, expected_extra=["gcp_billing_spend.png"],
        ui_dimensions=(1600, 1000), section03_dimensions=(1600, 900),
        output=None, strict_partial=True,
        allow_pending_producer_topic=None, workspace=root,
    )
    lax = capture.verify_screenshots_only(
        root=root, manifest=root / "ui_manifest.json", section03_manifest=None,
        expected_edai2_count=32, expected_extra=["gcp_billing_spend.png"],
        ui_dimensions=(1600, 1000), section03_dimensions=(1600, 900),
        output=None, strict_partial=False,
        allow_pending_producer_topic=None, workspace=root,
    )
    strict_by_name = {item["name"]: item["status"] for item in strict["files"]}
    assert strict_by_name["design_patterns.png"] == "PendingProducer"
    assert strict_by_name["whole_course_diagram.png"] == "PendingProducer"
    for name, status in strict_by_name.items():
        if name not in ("design_patterns.png", "whole_course_diagram.png"):
            assert status != "PendingProducer", name
    lax_by_name = {item["name"]: item["status"] for item in lax["files"]}
    assert lax_by_name["design_patterns.png"] == "Missing"
    assert lax_by_name["whole_course_diagram.png"] == "Missing"


def test_verify_screenshots_only_section03_hash_link(tmp_path: Path) -> None:
    """Section03 PNG must match its manifest sha256 at 1600x900."""
    capture = _load_script()
    s03dir = tmp_path / "s03"
    s03dir.mkdir()
    png = s03dir / "section03_config_and_training_join.png"
    _section03_png(png)
    import hashlib

    digest = hashlib.sha256(png.read_bytes()).hexdigest()
    manifest = tmp_path / "section03_manifest.json"
    manifest.write_text(json.dumps({
        "bundle_id": "b" * 64,
        "artifacts": {"evidence_image": {
            "path": "s03/" + png.name, "sha256": digest, "size_bytes": png.stat().st_size,
        }},
    }) + "\n", encoding="utf-8")
    shots = tmp_path / "shots"
    shots.mkdir()
    (shots / "ui_manifest.json").write_text("[]\n", encoding="utf-8")
    result = capture.verify_screenshots_only(
        root=shots, manifest=shots / "ui_manifest.json",
        section03_manifest=manifest,
        expected_edai2_count=32, expected_extra=["gcp_billing_spend.png"],
        ui_dimensions=(1600, 1000), section03_dimensions=(1600, 900),
        output=None, strict_partial=True,
        allow_pending_producer_topic=None, workspace=tmp_path,
    )
    s03 = [item for item in result["files"] if item.get("kind") == "section03"]
    assert len(s03) == 1 and s03[0]["status"] == "Pass"


# --- T31 Task 3: run_manifest.json strict-partial generation (TDD RED first) ---

def _run_manifest_cli(args: list[str]):
    import os
    import subprocess
    import sys

    src = str(ROOT / "src")
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/qa/capture_edai2_evidence.py"), *args],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )


def test_run_manifest_strict_partial_cli_exit_zero_and_valid_json(tmp_path: Path) -> None:
    """T31 run-manifest mode must exit 0 and write valid JSON with required keys."""
    out = tmp_path / "run_manifest.json"
    proc = _run_manifest_cli([
        "--strict-partial", "--allow-pending-producer-topic", "32",
        "--root", "evidence/04_2_llm_design",
        "--output", str(out),
    ])
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    for key in (
        "mode", "strict_partial", "allow_pending_producer_topic", "root",
        "revision", "cost", "capacity", "ttl", "backend_proof", "jobs",
        "screenshot_audit", "vault", "fingerprint", "completion_records",
        "visual_qa", "summary",
    ):
        assert key in payload, key


def test_run_manifest_pending_scoped_to_topic32_only(tmp_path: Path) -> None:
    """PendingProducer must be ONLY design_patterns + whole_course_diagram."""
    capture = _load_script()
    out = tmp_path / "run_manifest.json"
    manifest = capture.build_run_manifest(
        root=ROOT / "evidence/04_2_llm_design",
        allow_pending_producer_topic="32",
        strict_partial=True,
        output=out,
        workspace=ROOT,
    )
    audit = manifest["screenshot_audit"]
    assert audit["summary"]["fail"] == 0
    assert set(audit["pending"]).issubset({"design_patterns.png", "whole_course_diagram.png"})
    assert audit["summary"]["pending_producer"] == len(audit["pending"])
    assert out.is_file()
    assert json.loads(out.read_text(encoding="utf-8")) == manifest


def test_run_manifest_rerun_deterministic(tmp_path: Path) -> None:
    """Two runs must be byte-identical (same SHA)."""
    import hashlib

    capture = _load_script()
    out = tmp_path / "run_manifest.json"
    first = capture.build_run_manifest(
        root=ROOT / "evidence/04_2_llm_design",
        allow_pending_producer_topic="32",
        strict_partial=True,
        output=out,
        workspace=ROOT,
    )
    sha1 = hashlib.sha256(out.read_bytes()).hexdigest()
    second = capture.build_run_manifest(
        root=ROOT / "evidence/04_2_llm_design",
        allow_pending_producer_topic="32",
        strict_partial=True,
        output=tmp_path / "run_manifest2.json",
        workspace=ROOT,
    )
    sha2 = hashlib.sha256((tmp_path / "run_manifest2.json").read_bytes()).hexdigest()
    assert sha1 == sha2
    assert first == second


def test_run_manifest_read_only_inputs(tmp_path: Path) -> None:
    """Inputs (PNG/manifest/evidence) mtimes unchanged; only outputs written."""
    capture = _load_script()
    watched = [
        ROOT / "evidence/04_2_llm_design/gke/cost_forecast_topic31.json",
        ROOT / "evidence/04_2_llm_design/cicd/jobs.json",
        ROOT / "evidence/04_2_llm_design/gke/persistence_before.json",
        ROOT / "evidence/03_data_generator_improvement/section03_manifest.json",
    ]
    watched = [p for p in watched if p.is_file()]
    before = {str(p): p.stat().st_mtime_ns for p in watched}
    audit_tmp = tmp_path / "audit.json"
    capture.verify_screenshots_only(
        root=ROOT / "evidence/04_2_llm_design",
        manifest=ROOT / "evidence/04_2_llm_design/screenshots/ui_manifest.json",
        section03_manifest=ROOT / "evidence/03_data_generator_improvement/section03_manifest.json",
        expected_edai2_count=32, expected_extra=["gcp_billing_spend.png"],
        ui_dimensions=(1600, 1000), section03_dimensions=(1600, 900),
        output=audit_tmp, strict_partial=True,
        allow_pending_producer_topic="32", workspace=ROOT,
    )
    out = tmp_path / "run_manifest.json"
    capture.build_run_manifest(
        root=ROOT / "evidence/04_2_llm_design",
        allow_pending_producer_topic="32",
        strict_partial=True,
        output=out,
        workspace=ROOT,
    )
    for p in watched:
        assert p.stat().st_mtime_ns == before[str(p)], p
    assert out.is_file() and audit_tmp.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["vault"]["status"] == "Present"
    assert payload["vault"]["sha256"] == "036a495352a1a3ec2c14b5bb1ed8d0052f95af336f9dc19aec60334a2942566b"
    assert payload["fingerprint"]["deferred_count"] == 7
    assert payload["jobs"]["digest_match_count"] == 6
    assert payload["visual_qa"]["status"] == "pass"
    assert payload["visual_qa"]["reviewer"] == "agent (operator-delegated)"


# --- T31 Task 2: repair-CLI remainder (merge_review + recapture, TDD) ---

def test_merge_review_accepts_reviewer_pass_reason() -> None:
    capture = _load_script()
    out = capture.merge_review(
        audit={"a.png": {"status": "Pass"}},
        reviews=[{"path": "a.png", "reviewer": "op", "result": "pass", "reason": "selectors legible"}],
    )
    assert out["a.png"]["visual"] == "pass"


def test_recapture_rejects_without_reachability_policy() -> None:
    capture = _load_script()
    assert capture.recapture(["a.png"], policy=None) == {"a.png": "deferred-no-policy"}

def test_local_render_source_is_accepted_for_topic32(tmp_path: Path) -> None:
    """Topic 32 diagrams are source-rendered; only their exact names may use local-render."""
    capture = _load_script()
    root = tmp_path
    capture.record_capture(
        final_path=root / "design_patterns.png", root=root, writer=_writer(11),
        source="local-render:scripts/qa/render_topic32_diagrams.py", revision=REVISION,
        visible_selectors=list(capture.REQUIRED_VIEWS["design_patterns.png"]),
        machine_evidence=[_machine(root, "topic32_source.json")],
        proves="Proves the design-pattern diagram is source-rendered.",
        does_not_prove="It does not prove runtime behavior.",
        manifest_path=root / "ui_manifest.json", workspace=root,
    )
    entry = json.loads((root / "ui_manifest.json").read_text(encoding="utf-8"))[0]
    assert entry["url_or_source"].startswith("local-render:")


def test_local_render_source_is_rejected_for_other_views(tmp_path: Path) -> None:
    """Only the two Topic 32 producer images may claim local-render provenance."""
    capture = _load_script()
    root = tmp_path
    with pytest.raises(ValueError, match="unsafe"):
        capture.record_capture(
            final_path=root / "airflow_rag_graph.png", root=root, writer=_writer(12),
            source="local-render:scripts/qa/render_topic32_diagrams.py", revision=REVISION,
            visible_selectors=list(capture.REQUIRED_VIEWS["airflow_rag_graph.png"]),
            machine_evidence=[_machine(root, "topic32_source.json")],
            proves="Proves the view is contextual.",
            does_not_prove="It does not prove unrelated gates.",
            manifest_path=root / "ui_manifest.json", workspace=root,
        )
