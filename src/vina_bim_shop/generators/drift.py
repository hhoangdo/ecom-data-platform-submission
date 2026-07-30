from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from vina_bim_shop.generators.config import DriftConfig, GeneratorConfig
from vina_bim_shop.generators.profiles import random_timestamps, time_bounds


_EVENING_HOURLY_WEIGHTS = np.array(
    [
        0.015,
        0.01,
        0.008,
        0.006,
        0.006,
        0.01,
        0.02,
        0.035,
        0.04,
        0.04,
        0.045,
        0.05,
        0.07,
        0.05,
        0.045,
        0.045,
        0.055,
        0.07,
        0.085,
        0.09,
        0.09,
        0.065,
        0.04,
        0.025,
    ],
    dtype=float,
)
_CHILD_RNG_NAMESPACE = b"section03-order-timestamps-v1\0"


@dataclass(frozen=True)
class DriftWindow:
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    drift_start_ts: pd.Timestamp
    feature_cutoff_ts: pd.Timestamp
    label_end_ts: pd.Timestamp
    baseline_date: date


@dataclass(frozen=True)
class DriftRateSummary:
    pre_count: int
    post_count: int
    pre_duration_days: float
    post_duration_days: float
    pre_rate_per_day: float
    post_rate_per_day: float
    normalized_post_pre_ratio: float


def _round_half_even_12(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_EVEN))


def calculate_psi(
    baseline: pd.Series,
    current: pd.Series,
    *,
    quantile_bins: int = 10,
    epsilon: float = 1e-6,
) -> float:
    if isinstance(quantile_bins, bool) or quantile_bins < 2:
        raise ValueError("quantile_bins must be at least 2")
    if not np.isfinite(epsilon) or not 0 < epsilon < 1:
        raise ValueError("epsilon must be between 0 and 1")

    def finite_values(values: pd.Series, name: str) -> np.ndarray:
        numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype=np.float64)
        numeric = numeric[np.isfinite(numeric)]
        if numeric.size == 0:
            raise ValueError(f"{name} must contain a finite value")
        return numeric

    baseline_values = np.sort(finite_values(baseline, "baseline"))
    current_values = finite_values(current, "current")
    quantiles = np.linspace(0.0, 1.0, quantile_bins + 1)
    positions = (baseline_values.size - 1) * quantiles
    lower = np.floor(positions).astype(int)
    upper = np.minimum(lower + 1, baseline_values.size - 1)
    fractions = positions - lower
    type_7_edges = baseline_values[lower] + fractions * (
        baseline_values[upper] - baseline_values[lower]
    )
    effective_edges = np.unique(type_7_edges)
    shifted_edges = np.nextafter(effective_edges, np.inf)
    histogram_edges = np.concatenate(([-np.inf], shifted_edges, [np.inf]))

    baseline_counts, _ = np.histogram(baseline_values, bins=histogram_edges)
    current_counts, _ = np.histogram(current_values, bins=histogram_edges)
    baseline_p = baseline_counts.astype(np.float64) / baseline_values.size
    current_p = current_counts.astype(np.float64) / current_values.size
    baseline_p = np.where(baseline_p == 0, epsilon, baseline_p)
    current_p = np.where(current_p == 0, epsilon, current_p)
    baseline_p /= baseline_p.sum()
    current_p /= current_p.sum()
    value = float(np.sum((current_p - baseline_p) * np.log(current_p / baseline_p)))
    if not np.isfinite(value):
        raise ValueError("PSI calculation produced a nonfinite value")
    rounded = _round_half_even_12(value)
    return 0.0 if rounded == 0.0 else rounded


def resolve_drift_window(config: GeneratorConfig) -> DriftWindow:
    start_ts, end_ts, _ = time_bounds(config)
    drift_start_ts = start_ts + (end_ts - start_ts) * config.drift.cutoff_fraction
    feature_cutoff_ts = end_ts - pd.Timedelta(days=config.drift.label_horizon_days)
    label_end_ts = feature_cutoff_ts + pd.Timedelta(days=config.drift.label_horizon_days)
    baseline_date = (drift_start_ts.floor("D") - pd.Timedelta(days=1)).date()
    baseline_start_ts = pd.Timestamp(baseline_date) - pd.Timedelta(days=6)
    if config.drift.enabled and start_ts > baseline_start_ts:
        raise ValueError("drift requires seven complete baseline days")
    return DriftWindow(
        start_ts=start_ts,
        end_ts=end_ts,
        drift_start_ts=drift_start_ts,
        feature_cutoff_ts=feature_cutoff_ts,
        label_end_ts=label_end_ts,
        baseline_date=baseline_date,
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot canonicalize RNG state value {type(value).__name__}")


def _child_seed(rng: np.random.Generator) -> int:
    state = json.dumps(
        rng.bit_generator.state,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(_CHILD_RNG_NAMESPACE + state).digest()
    return int.from_bytes(digest, "big")


def generate_order_timestamps_with_drift(
    rng: np.random.Generator,
    *,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    size: int,
    drift: DriftConfig,
) -> pd.Series:
    if not drift.enabled:
        return random_timestamps(rng, start_ts, end_ts, size, evening_bias=True)

    child_rng = np.random.default_rng(_child_seed(rng))
    random_timestamps(rng, start_ts, end_ts, size, evening_bias=True)

    minute_slots = pd.date_range(start_ts.floor("min"), end_ts.floor("min"), freq="min")
    drift_start_ts = start_ts + (end_ts - start_ts) * drift.cutoff_fraction
    raw_weights = _EVENING_HOURLY_WEIGHTS[np.asarray(minute_slots.hour)]
    raw_weights = raw_weights * np.where(
        minute_slots >= drift_start_ts,
        drift.post_rate_multiplier,
        1.0,
    )
    probabilities = raw_weights / raw_weights.sum()
    indices = child_rng.choice(
        len(minute_slots),
        size=size,
        replace=True,
        p=probabilities,
    )
    seconds = child_rng.integers(0, 60, size=size)
    timestamps = pd.Series(minute_slots.take(indices)) + pd.to_timedelta(seconds, unit="s")
    return timestamps.clip(lower=start_ts, upper=end_ts)


def summarize_drift_rates(
    timestamps: pd.Series,
    *,
    window: DriftWindow,
) -> DriftRateSummary:
    parsed = pd.to_datetime(timestamps, errors="raise")
    pre_count = int((parsed < window.drift_start_ts).sum())
    post_count = int((parsed >= window.drift_start_ts).sum())
    if pre_count == 0:
        raise ValueError("timestamps must contain a pre-drift row")
    if post_count == 0:
        raise ValueError("timestamps must contain a post-drift row")

    pre_duration_days = (window.drift_start_ts - window.start_ts).total_seconds() / 86_400
    post_duration_days = (window.end_ts - window.drift_start_ts).total_seconds() / 86_400
    if pre_duration_days <= 0 or post_duration_days <= 0:
        raise ValueError("drift window durations must be positive")

    pre_rate_per_day = pre_count / pre_duration_days
    post_rate_per_day = post_count / post_duration_days
    return DriftRateSummary(
        pre_count=pre_count,
        post_count=post_count,
        pre_duration_days=pre_duration_days,
        post_duration_days=post_duration_days,
        pre_rate_per_day=pre_rate_per_day,
        post_rate_per_day=post_rate_per_day,
        normalized_post_pre_ratio=post_rate_per_day / pre_rate_per_day,
    )
