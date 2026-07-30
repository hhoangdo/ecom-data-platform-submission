from __future__ import annotations

import inspect
import json
from pathlib import Path

import pandas as pd
from PIL import Image
import yaml

from vina_bim_shop.generators.runner import run_generation


EXPECTED_SIGNATURE = (
    "(*, config_path: 'str | Path', scale: 'str', mode: 'GenerationMode', "
    "raw_root: 'str | Path | None' = None, evidence_root: 'str | Path | None' = None, "
    "seed: 'int | None' = None, clean: 'bool' = False, publish_kafka: 'bool' = False, "
    "kafka_bootstrap_servers: 'str | None' = None, "
    "kafka_flush_timeout_seconds: 'float' = 30.0) -> 'GenerationResult'"
)
REPORT_HEADINGS = [
    "Run Context",
    "Scenario and Rationale",
    "Fixed Counts",
    "Realized Pre/Post Rates",
    "Point-in-Time and Label Policy",
    "Daily PSI Summary",
    "Alerts",
    "Exact Label Contract",
    "Feast-ready Training Join",
    "Quality Checks",
    "Spark/dbt Parity Runtime",
    "Airflow DP3 Runtime",
    "DataHub Lineage Runtime",
    "Sheet3 E32-E34 Evidence",
    "Reproduction Commands",
    "Limitations",
]


def test_section03_smoke_candidate_contract_and_section01_preservation(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    evidence_root = tmp_path / "evidence"

    result = run_generation(
        config_path=repo_root / "configs" / "generator" / "base.yaml",
        scale="smoke",
        mode="full",
        raw_root=tmp_path / "raw",
        evidence_root=evidence_root,
        clean=True,
        seed=42,
    )

    assert str(inspect.signature(run_generation)) == EXPECTED_SIGNATURE
    assert result.evidence_root == evidence_root
    assert (evidence_root / "run_manifest.json").is_file()
    candidate_path = evidence_root / "section03" / "section03_candidate_manifest.json"
    assert result.evidence_paths["section03_manifest"] == candidate_path
    assert candidate_path.is_file()
    assert not (evidence_root / "section03" / "section03_manifest.json").exists()

    manifest = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert manifest["runtime_evidence"] == {
        "status": "pending",
        "spark": None,
        "airflow": None,
        "datahub": None,
    }
    assert set(manifest["rubric_cells"]) == {"E32", "E33", "E34"}
    assert [manifest["rubric_cells"][cell]["points"] for cell in ("E32", "E33", "E34")] == [1, 1, 2]
    assert {value["status"] for value in manifest["rubric_cells"].values()} == {"Candidate"}
    assert all(manifest["checks"].values())

    bundle_root = evidence_root / "section03" / "runs" / manifest["bundle_id"]
    labels = pd.read_csv(bundle_root / "ml_customer_label.csv")
    health = pd.read_csv(bundle_root / "agg_feature_health_daily.csv")
    alerts = pd.read_csv(bundle_root / "feature_drift_alerts.csv")
    training = pd.read_csv(bundle_root / "ml_customer_purchase_training.csv")
    assert list(labels.columns) == ["id", "label"]
    assert labels["id"].is_unique and labels["label"].isin([0, 1]).all()
    assert labels[["id", "label"]].equals(training[["id", "label"]])
    assert list(health.columns) == manifest["artifacts"]["feature_health_daily"]["columns"]
    assert pd.to_numeric(health["psi_vs_baseline"]).map(pd.notna).all()
    assert alerts.empty or (alerts["psi_value"] >= 0.15).all()
    assert training["id"].is_unique and not training.empty

    with Image.open(bundle_root / "section03_config_and_training_join.png") as image:
        image.verify()
    with Image.open(bundle_root / "section03_config_and_training_join.png") as image:
        assert image.size == (1600, 900)
    report = (bundle_root / "section03_report.md").read_text(encoding="utf-8")
    assert [line[3:] for line in report.splitlines() if line.startswith("## ")] == REPORT_HEADINGS
    assert report.count("Pending") >= 3


def test_disabled_drift_emits_no_section03_tree_or_keys(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load(
        (repo_root / "configs" / "generator" / "base.yaml").read_text(encoding="utf-8")
    )
    config["drift"]["enabled"] = False
    config["taxonomy"]["source_path"] = str(
        (repo_root / "data" / "reference" / "taxonomy" / "taxonomy_snapshot.yaml").resolve()
    )
    config_path = tmp_path / "base.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    result = run_generation(
        config_path=config_path,
        scale="smoke",
        mode="offline",
        raw_root=tmp_path / "raw",
        evidence_root=tmp_path / "evidence",
        clean=True,
        seed=42,
    )

    assert not (tmp_path / "evidence" / "section03").exists()
    assert not any(key.startswith("section03_") for key in result.evidence_paths)
    assert (tmp_path / "evidence" / "run_manifest.json").is_file()
