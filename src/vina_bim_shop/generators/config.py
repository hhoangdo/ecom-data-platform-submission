from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Literal, cast

import yaml


DriftScenario = Literal["customer_order_frequency"]
DriftMode = Literal["abrupt"]


@dataclass(frozen=True)
class DriftConfig:
    enabled: bool
    scenario: DriftScenario
    mode: DriftMode
    cutoff_fraction: float
    post_rate_multiplier: float
    psi_warning: float
    psi_alert: float
    label_horizon_days: int


@dataclass(frozen=True)
class Taxonomy:
    level_1_categories: list[str]
    category_names: dict[str, str]
    subcategories: dict[str, list[str]]


@dataclass(frozen=True)
class GeneratorConfig:
    platform_name: str
    random_seed: int
    scale: str
    history_days: int
    end_date: str
    entities: dict[str, int]
    raw_root: Path
    evidence_root: Path
    taxonomy: Taxonomy
    category_weights: dict[str, float]
    geography: dict[str, Any]
    customer_segments: dict[str, dict[str, Any]]
    seller_tiers: dict[str, dict[str, Any]]
    quality: dict[str, Any]
    streaming: dict[str, Any]
    kafka: dict[str, Any]
    source_config_path: Path
    drift: DriftConfig
    section03_evidence_root: Path


def _repo_root_from_config(config_path: Path) -> Path:
    return config_path.resolve().parents[2]


def _resolve_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return data


def _load_taxonomy(path: Path) -> Taxonomy:
    data = _load_yaml(path)
    categories = data.get("level_1_categories", [])
    level_1: list[str] = []
    names: dict[str, str] = {}
    subcategories: dict[str, list[str]] = {}
    for item in categories:
        code = str(item["category_code"])
        level_1.append(code)
        names[code] = str(item["category_name"])
        subcategories[code] = [str(value) for value in item.get("subcategories", [])]
    return Taxonomy(level_1_categories=level_1, category_names=names, subcategories=subcategories)


def _normalise_weights(weights: dict[str, Any]) -> dict[str, float]:
    total = float(sum(float(value) for value in weights.values()))
    if total <= 0:
        raise ValueError("Weights must sum to a positive number")
    return {str(key): float(value) / total for key, value in weights.items()}


def _parse_drift_config(value: Any) -> DriftConfig:
    if not isinstance(value, Mapping):
        raise ValueError("drift must be a mapping")

    required_keys = (
        "enabled",
        "scenario",
        "mode",
        "cutoff_fraction",
        "post_rate_multiplier",
        "psi_warning",
        "psi_alert",
        "label_horizon_days",
    )
    for key in required_keys:
        if key not in value:
            raise ValueError(f"drift.{key} is required")
    for key in value:
        if key not in required_keys:
            raise ValueError(f"drift.{key} is not allowed")

    enabled = value["enabled"]
    if not isinstance(enabled, bool):
        raise ValueError("drift.enabled must be a boolean")

    scenario = value["scenario"]
    if scenario != "customer_order_frequency":
        raise ValueError("drift.scenario must equal 'customer_order_frequency'")

    mode = value["mode"]
    if mode != "abrupt":
        raise ValueError("drift.mode must equal 'abrupt'")

    def fixed_float(key: str, expected: float) -> float:
        candidate = value[key]
        if (
            isinstance(candidate, bool)
            or not isinstance(candidate, (int, float))
            or not math.isfinite(float(candidate))
            or float(candidate) != expected
        ):
            raise ValueError(f"drift.{key} must equal {expected}")
        return float(candidate)

    label_horizon_days = value["label_horizon_days"]
    if (
        isinstance(label_horizon_days, bool)
        or not isinstance(label_horizon_days, int)
        or label_horizon_days != 7
    ):
        raise ValueError("drift.label_horizon_days must equal 7")

    return DriftConfig(
        enabled=enabled,
        scenario=cast(DriftScenario, scenario),
        mode=cast(DriftMode, mode),
        cutoff_fraction=fixed_float("cutoff_fraction", 0.65),
        post_rate_multiplier=fixed_float("post_rate_multiplier", 1.5),
        psi_warning=fixed_float("psi_warning", 0.1),
        psi_alert=fixed_float("psi_alert", 0.15),
        label_horizon_days=label_horizon_days,
    )


def load_generator_config(
    config_path: str | Path,
    *,
    scale: str | None = None,
    raw_root: str | Path | None = None,
    evidence_root: str | Path | None = None,
    seed: int | None = None,
) -> GeneratorConfig:
    config_path = Path(config_path).resolve()
    repo_root = _repo_root_from_config(config_path)
    data = _load_yaml(config_path)

    selected_scale = scale or str(data.get("default_scale", "medium"))
    scale_profiles = data.get("scale_profiles", {})
    if selected_scale not in scale_profiles:
        valid = ", ".join(sorted(scale_profiles))
        raise ValueError(f"Unknown scale '{selected_scale}'. Expected one of: {valid}")
    profile = scale_profiles[selected_scale]

    outputs = data.get("outputs", {})
    taxonomy_path = _resolve_path(repo_root, data["taxonomy"]["source_path"])
    resolved_evidence_root = _resolve_path(repo_root, evidence_root or outputs["evidence_root"])
    section03_evidence_root = (
        resolved_evidence_root / "section03"
        if evidence_root is not None
        else _resolve_path(repo_root, outputs["section03_evidence_root"])
    )

    return GeneratorConfig(
        platform_name=str(data["platform_name"]),
        random_seed=int(seed if seed is not None else data.get("random_seed", 42)),
        scale=selected_scale,
        history_days=int(profile["history_days"]),
        end_date=str(data["end_date"]),
        entities={str(key): int(value) for key, value in profile["entities"].items()},
        raw_root=_resolve_path(repo_root, raw_root or outputs["raw_root"]),
        evidence_root=resolved_evidence_root,
        taxonomy=_load_taxonomy(taxonomy_path),
        category_weights=_normalise_weights(data["category_weights"]),
        geography=data["geography"],
        customer_segments=data["customer_segments"],
        seller_tiers=data["seller_tiers"],
        quality=data["quality_scenarios"],
        streaming=data["streaming"],
        kafka=data["kafka"],
        source_config_path=config_path,
        drift=_parse_drift_config(data.get("drift")),
        section03_evidence_root=section03_evidence_root,
    )
