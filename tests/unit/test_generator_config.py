from dataclasses import FrozenInstanceError
from pathlib import Path
import shutil
from typing import Any

import pytest
import yaml

from vina_bim_shop.generators.config import DriftConfig
from vina_bim_shop.generators.config import load_generator_config


APPROVED_DRIFT = {
    "enabled": True,
    "scenario": "customer_order_frequency",
    "mode": "abrupt",
    "cutoff_fraction": 0.65,
    "post_rate_multiplier": 1.5,
    "psi_warning": 0.10,
    "psi_alert": 0.15,
    "label_horizon_days": 7,
}


def _write_config(tmp_path: Path, drift: Any) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "configs" / "generator" / "base.yaml"
    config = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    config["drift"] = drift

    config_path = tmp_path / "configs" / "generator" / "base.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    taxonomy_source = repo_root / "data" / "reference" / "taxonomy" / "taxonomy_snapshot.yaml"
    taxonomy_path = tmp_path / "data" / "reference" / "taxonomy" / "taxonomy_snapshot.yaml"
    taxonomy_path.parent.mkdir(parents=True)
    shutil.copyfile(taxonomy_source, taxonomy_path)
    return config_path


def test_load_generator_config_applies_scale_and_output_overrides(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    config = load_generator_config(
        repo_root / "configs" / "generator" / "base.yaml",
        scale="smoke",
        raw_root=tmp_path / "raw",
        evidence_root=tmp_path / "evidence",
        seed=123,
    )

    assert config.platform_name == "vina-bim-shop"
    assert config.random_seed == 123
    assert config.history_days == 14
    assert config.entities == {
        "customers": 800,
        "sellers": 80,
        "products": 600,
        "orders": 1800,
        "promotions": 16,
    }
    assert config.raw_root == tmp_path / "raw"
    assert config.evidence_root == tmp_path / "evidence"
    assert config.section03_evidence_root == tmp_path / "evidence" / "section03"
    assert config.drift == DriftConfig(**APPROVED_DRIFT)
    assert config.category_weights["FMCG"] > config.category_weights["Fashion"]
    assert "FMCG" in config.taxonomy.level_1_categories
    assert "Health & Beauty" in config.taxonomy.subcategories["FMCG"]
    assert set(config.kafka["topics"]) == {
        "commerce_events",
        "catalog_events",
        "fulfillment_events",
        "ops_events",
    }
    assert config.kafka["event_format"] == "json"
    assert config.kafka["consumer_freshness_targets"]["executive_teams_minutes"] == 60


def test_load_generator_config_uses_canonical_section03_root() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    config = load_generator_config(repo_root / "configs" / "generator" / "base.yaml")

    assert config.section03_evidence_root == repo_root / "evidence" / "03_data_generator_improvement"
    assert config.history_days == 60
    assert config.entities["orders"] == 45_000


def test_drift_config_is_frozen() -> None:
    drift = DriftConfig(**APPROVED_DRIFT)

    with pytest.raises(FrozenInstanceError):
        drift.enabled = False  # type: ignore[misc]


@pytest.mark.parametrize("missing_key", list(APPROVED_DRIFT))
def test_load_generator_config_rejects_each_missing_drift_key(
    tmp_path: Path,
    missing_key: str,
) -> None:
    drift = dict(APPROVED_DRIFT)
    drift.pop(missing_key)

    with pytest.raises(ValueError, match=rf"^drift\.{missing_key} is required$"):
        load_generator_config(_write_config(tmp_path, drift))


@pytest.mark.parametrize("unknown_key", ["extra", 123])
def test_load_generator_config_rejects_unknown_drift_key(
    tmp_path: Path,
    unknown_key: str | int,
) -> None:
    drift = {**APPROVED_DRIFT, unknown_key: "not-approved"}

    with pytest.raises(ValueError, match=rf"^drift\.{unknown_key} is not allowed$"):
        load_generator_config(_write_config(tmp_path, drift))


def test_load_generator_config_rejects_mixed_type_unknown_drift_keys(
    tmp_path: Path,
) -> None:
    drift = {**APPROVED_DRIFT, "extra": "not-approved", 123: "not-approved"}

    with pytest.raises(ValueError, match=r"^drift\.(extra|123) is not allowed$"):
        load_generator_config(_write_config(tmp_path, drift))


@pytest.mark.parametrize("value", [None, [], "enabled"])
def test_load_generator_config_rejects_non_mapping_drift(tmp_path: Path, value: Any) -> None:
    with pytest.raises(ValueError, match=r"^drift must be a mapping$"):
        load_generator_config(_write_config(tmp_path, value))


@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_load_generator_config_rejects_non_boolean_enabled(tmp_path: Path, value: Any) -> None:
    drift = {**APPROVED_DRIFT, "enabled": value}

    with pytest.raises(ValueError, match=r"^drift\.enabled must be a boolean$"):
        load_generator_config(_write_config(tmp_path, drift))


@pytest.mark.parametrize(
    ("field", "value", "required"),
    [
        ("scenario", "order_value", "'customer_order_frequency'"),
        ("mode", "gradual", "'abrupt'"),
        ("cutoff_fraction", 0.50, "0.65"),
        ("post_rate_multiplier", 2.0, "1.5"),
        ("psi_warning", 0.09, "0.1"),
        ("psi_alert", 0.16, "0.15"),
        ("label_horizon_days", 8, "7"),
    ],
)
def test_load_generator_config_rejects_unapproved_drift_values(
    tmp_path: Path,
    field: str,
    value: Any,
    required: str,
) -> None:
    drift = {**APPROVED_DRIFT, field: value}

    with pytest.raises(ValueError, match=rf"^drift\.{field} must equal {required}$"):
        load_generator_config(_write_config(tmp_path, drift))


@pytest.mark.parametrize(
    ("field", "value", "required"),
    [
        ("cutoff_fraction", True, "0.65"),
        ("cutoff_fraction", float("nan"), "0.65"),
        ("cutoff_fraction", float("inf"), "0.65"),
        ("post_rate_multiplier", True, "1.5"),
        ("post_rate_multiplier", float("nan"), "1.5"),
        ("post_rate_multiplier", float("inf"), "1.5"),
        ("psi_warning", True, "0.1"),
        ("psi_warning", float("nan"), "0.1"),
        ("psi_warning", float("inf"), "0.1"),
        ("psi_alert", True, "0.15"),
        ("psi_alert", float("nan"), "0.15"),
        ("psi_alert", float("inf"), "0.15"),
        ("label_horizon_days", True, "7"),
        ("label_horizon_days", float("nan"), "7"),
        ("label_horizon_days", float("inf"), "7"),
    ],
)
def test_load_generator_config_rejects_boolean_or_nonfinite_numeric_values(
    tmp_path: Path,
    field: str,
    value: Any,
    required: str,
) -> None:
    drift = {**APPROVED_DRIFT, field: value}

    with pytest.raises(ValueError, match=rf"^drift\.{field} must equal {required}$"):
        load_generator_config(_write_config(tmp_path, drift))
