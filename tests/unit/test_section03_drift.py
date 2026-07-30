from __future__ import annotations

from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from vina_bim_shop.generators import drift as drift_module
from vina_bim_shop.generators.config import GeneratorConfig, load_generator_config
from vina_bim_shop.generators.drift import (
    DriftRateSummary,
    DriftWindow,
    generate_order_timestamps_with_drift,
    resolve_drift_window,
    summarize_drift_rates,
)
from vina_bim_shop.generators.offline import orders as orders_module
from vina_bim_shop.generators.offline.generator import generate_offline
from vina_bim_shop.generators.profiles import random_timestamps
from vina_bim_shop.generators.streaming.generator import generate_streaming_events
from vina_bim_shop.generators.writer import write_raw_outputs


HOURLY_WEIGHTS = np.array(
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


def _config(*, scale: str = "smoke") -> GeneratorConfig:
    repo_root = Path(__file__).resolve().parents[2]
    return load_generator_config(repo_root / "configs" / "generator" / "base.yaml", scale=scale)


def _state_json(rng: np.random.Generator) -> str:
    return json.dumps(rng.bit_generator.state, sort_keys=True, separators=(",", ":"))


def _legacy_timestamp_hook(
    rng: np.random.Generator,
    *,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    size: int,
    drift: Any,
) -> pd.Series:
    del drift
    return random_timestamps(rng, start_ts, end_ts, size, evening_bias=True)


def test_resolve_drift_window_uses_configuration_boundaries() -> None:
    window = resolve_drift_window(_config())

    assert window == DriftWindow(
        start_ts=pd.Timestamp("2026-04-18T23:59:00"),
        end_ts=pd.Timestamp("2026-05-01T23:59:00"),
        drift_start_ts=pd.Timestamp("2026-04-27T10:47:00"),
        feature_cutoff_ts=pd.Timestamp("2026-04-24T23:59:00"),
        label_end_ts=pd.Timestamp("2026-05-01T23:59:00"),
        baseline_date=date(2026, 4, 26),
    )


def test_resolve_drift_window_rejects_insufficient_enabled_baseline() -> None:
    config = replace(_config(), history_days=7)

    with pytest.raises(ValueError, match="^drift requires seven complete baseline days$"):
        resolve_drift_window(config)


def test_disabled_sampler_delegates_before_validating_or_allocating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = pd.Series(["legacy"])
    calls: list[tuple[Any, ...]] = []

    def fake_legacy(*args: Any, **kwargs: Any) -> pd.Series:
        calls.append((*args, kwargs))
        return sentinel

    monkeypatch.setattr(drift_module, "random_timestamps", fake_legacy)
    config = replace(_config(), drift=replace(_config().drift, enabled=False))
    rng = np.random.default_rng(1)

    result = generate_order_timestamps_with_drift(
        rng,
        start_ts="invalid-start",  # type: ignore[arg-type]
        end_ts="invalid-end",  # type: ignore[arg-type]
        size=-1,
        drift=config.drift,
    )

    assert result is sentinel
    assert calls == [(rng, "invalid-start", "invalid-end", -1, {"evening_bias": True})]


def test_enabled_sampler_uses_namespaced_canonical_state_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(123)
    state = _state_json(rng).encode("utf-8")
    expected_seed = int.from_bytes(
        hashlib.sha256(b"section03-order-timestamps-v1\0" + state).digest(),
        "big",
    )
    real_default_rng = np.random.default_rng
    observed_seeds: list[int] = []

    def recording_default_rng(seed: int) -> np.random.Generator:
        observed_seeds.append(seed)
        return real_default_rng(seed)

    monkeypatch.setattr(drift_module.np.random, "default_rng", recording_default_rng)

    generate_order_timestamps_with_drift(
        rng,
        start_ts=pd.Timestamp("2026-01-01T00:00:00"),
        end_ts=pd.Timestamp("2026-01-01T00:05:00"),
        size=3,
        drift=_config().drift,
    )

    assert observed_seeds == [expected_seed]


def test_enabled_sampler_advances_shared_rng_like_one_legacy_call() -> None:
    actual_rng = np.random.default_rng(456)
    expected_rng = np.random.default_rng(456)
    start_ts = pd.Timestamp("2026-01-01T00:00:00")
    end_ts = pd.Timestamp("2026-01-03T23:59:00")

    generate_order_timestamps_with_drift(
        actual_rng,
        start_ts=start_ts,
        end_ts=end_ts,
        size=250,
        drift=_config().drift,
    )
    random_timestamps(expected_rng, start_ts, end_ts, 250, evening_bias=True)

    assert _state_json(actual_rng) == _state_json(expected_rng)


def test_enabled_sampler_uses_inclusive_slots_normalized_weights_and_draw_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}
    shared_rng = np.random.default_rng(2)

    class ChildRng:
        def choice(
            self,
            slots: int,
            *,
            size: int,
            replace: bool,
            p: np.ndarray,
        ) -> np.ndarray:
            observed.update(slots=slots, size=size, replace=replace, probabilities=p.copy())
            return np.array([0, 2])

        def integers(self, low: int, high: int, *, size: int) -> np.ndarray:
            observed.update(seconds_low=low, seconds_high=high, seconds_size=size)
            return np.array([59, 59])

    monkeypatch.setattr(drift_module.np.random, "default_rng", lambda seed: ChildRng())

    result = generate_order_timestamps_with_drift(
        shared_rng,
        start_ts=pd.Timestamp("2026-01-01T00:00:30"),
        end_ts=pd.Timestamp("2026-01-01T00:02:10"),
        size=2,
        drift=_config().drift,
    )

    assert observed["slots"] == 3
    assert observed["size"] == 2
    assert observed["replace"] is True
    np.testing.assert_allclose(observed["probabilities"], np.array([1.0, 1.0, 1.5]) / 3.5)
    assert observed["seconds_low"] == 0
    assert observed["seconds_high"] == 60
    assert observed["seconds_size"] == 2
    pd.testing.assert_series_equal(
        result,
        pd.Series(
            [
                pd.Timestamp("2026-01-01T00:00:59"),
                pd.Timestamp("2026-01-01T00:02:10"),
            ]
        ),
    )


def test_enabled_sampler_retains_legacy_hourly_weights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probabilities: list[np.ndarray] = []
    shared_rng = np.random.default_rng(3)

    class ChildRng:
        def choice(
            self,
            slots: int,
            *,
            size: int,
            replace: bool,
            p: np.ndarray,
        ) -> np.ndarray:
            del replace
            probabilities.append(p.copy())
            return np.zeros(size, dtype=int)

        def integers(self, low: int, high: int, *, size: int) -> np.ndarray:
            assert (low, high) == (0, 60)
            return np.zeros(size, dtype=int)

    monkeypatch.setattr(drift_module.np.random, "default_rng", lambda seed: ChildRng())

    generate_order_timestamps_with_drift(
        shared_rng,
        start_ts=pd.Timestamp("2026-01-01T00:00:00"),
        end_ts=pd.Timestamp("2026-01-01T02:00:00"),
        size=1,
        drift=_config().drift,
    )

    probability = probabilities[0]
    assert probability[0] / probability[60] == pytest.approx(HOURLY_WEIGHTS[0] / HOURLY_WEIGHTS[1])
    assert probability[78] / probability[60] == pytest.approx(1.5)


def test_enabled_sampler_is_reproducible_bounded_and_fixed_count() -> None:
    start_ts = pd.Timestamp("2026-01-01T00:00:30")
    end_ts = pd.Timestamp("2026-01-04T23:59:10")

    first = generate_order_timestamps_with_drift(
        np.random.default_rng(99),
        start_ts=start_ts,
        end_ts=end_ts,
        size=1_000,
        drift=_config().drift,
    )
    second = generate_order_timestamps_with_drift(
        np.random.default_rng(99),
        start_ts=start_ts,
        end_ts=end_ts,
        size=1_000,
        drift=_config().drift,
    )
    different = generate_order_timestamps_with_drift(
        np.random.default_rng(100),
        start_ts=start_ts,
        end_ts=end_ts,
        size=1_000,
        drift=_config().drift,
    )

    pd.testing.assert_series_equal(first, second)
    assert not first.equals(different)
    assert len(first) == 1_000
    assert first.between(start_ts, end_ts, inclusive="both").all()


def test_summarize_drift_rates_uses_exact_elapsed_seconds() -> None:
    window = DriftWindow(
        start_ts=pd.Timestamp("2026-01-01T00:00:00"),
        end_ts=pd.Timestamp("2026-01-05T00:00:00"),
        drift_start_ts=pd.Timestamp("2026-01-03T00:00:00"),
        feature_cutoff_ts=pd.Timestamp("2026-01-04T00:00:00"),
        label_end_ts=pd.Timestamp("2026-01-05T00:00:00"),
        baseline_date=date(2026, 1, 2),
    )
    timestamps = pd.Series(
        [
            pd.Timestamp("2026-01-01T12:00:00"),
            pd.Timestamp("2026-01-02T12:00:00"),
            pd.Timestamp("2026-01-03T00:00:00"),
            pd.Timestamp("2026-01-03T06:00:00"),
            pd.Timestamp("2026-01-03T12:00:00"),
            pd.Timestamp("2026-01-04T00:00:00"),
            pd.Timestamp("2026-01-04T06:00:00"),
            pd.Timestamp("2026-01-04T12:00:00"),
        ]
    )

    assert summarize_drift_rates(timestamps, window=window) == DriftRateSummary(
        pre_count=2,
        post_count=6,
        pre_duration_days=2.0,
        post_duration_days=2.0,
        pre_rate_per_day=1.0,
        post_rate_per_day=3.0,
        normalized_post_pre_ratio=3.0,
    )


@pytest.mark.parametrize(
    ("timestamps", "message"),
    [
        ([pd.Timestamp("2026-01-03T00:00:00")], "pre-drift"),
        ([pd.Timestamp("2026-01-02T00:00:00")], "post-drift"),
    ],
)
def test_summarize_drift_rates_rejects_empty_partition(
    timestamps: list[pd.Timestamp],
    message: str,
) -> None:
    window = DriftWindow(
        start_ts=pd.Timestamp("2026-01-01T00:00:00"),
        end_ts=pd.Timestamp("2026-01-05T00:00:00"),
        drift_start_ts=pd.Timestamp("2026-01-03T00:00:00"),
        feature_cutoff_ts=pd.Timestamp("2026-01-04T00:00:00"),
        label_end_ts=pd.Timestamp("2026-01-05T00:00:00"),
        baseline_date=date(2026, 1, 2),
    )

    with pytest.raises(ValueError, match=message):
        summarize_drift_rates(pd.Series(timestamps), window=window)


def test_medium_fixture_realized_rate_is_within_acceptance_interval() -> None:
    config = _config(scale="medium")
    window = resolve_drift_window(config)
    timestamps = generate_order_timestamps_with_drift(
        np.random.default_rng(config.random_seed),
        start_ts=window.start_ts,
        end_ts=window.end_ts,
        size=config.entities["orders"],
        drift=config.drift,
    )

    summary = summarize_drift_rates(timestamps, window=window)

    assert summary.pre_count + summary.post_count == 45_000
    assert 1.35 <= summary.normalized_post_pre_ratio <= 1.65


def test_disabled_generation_matches_legacy_frames_and_writer_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    config = replace(config, drift=replace(config.drift, enabled=False))
    actual_hook = orders_module.generate_order_timestamps_with_drift

    monkeypatch.setattr(orders_module, "generate_order_timestamps_with_drift", _legacy_timestamp_hook)
    expected = generate_offline(config)
    monkeypatch.setattr(orders_module, "generate_order_timestamps_with_drift", actual_hook)
    actual = generate_offline(config)

    assert expected.issue_records == actual.issue_records
    assert expected.datasets.keys() == actual.datasets.keys()
    for name in expected.datasets:
        pd.testing.assert_frame_equal(expected.datasets[name], actual.datasets[name], check_exact=True)

    expected_root = tmp_path / "expected"
    actual_root = tmp_path / "actual"
    write_raw_outputs(expected_root, expected.datasets, {})
    write_raw_outputs(actual_root, actual.datasets, {})
    expected_files = sorted(path.relative_to(expected_root) for path in expected_root.rglob("*") if path.is_file())
    actual_files = sorted(path.relative_to(actual_root) for path in actual_root.rglob("*") if path.is_file())
    assert expected_files == actual_files
    for relative_path in expected_files:
        assert (expected_root / relative_path).read_bytes() == (actual_root / relative_path).read_bytes()


def test_enabled_generation_changes_only_timestamp_derived_offline_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config()
    actual_hook = orders_module.generate_order_timestamps_with_drift

    monkeypatch.setattr(orders_module, "generate_order_timestamps_with_drift", _legacy_timestamp_hook)
    expected = generate_offline(config)
    expected_stream = generate_streaming_events(config, expected.datasets)
    monkeypatch.setattr(orders_module, "generate_order_timestamps_with_drift", actual_hook)
    actual = generate_offline(config)
    actual_stream = generate_streaming_events(config, actual.datasets)

    assert expected.issue_records == actual.issue_records
    for name in [
        "customers",
        "sellers",
        "products",
        "product_category_map",
        "inventory_snapshots",
        "promotions",
    ]:
        pd.testing.assert_frame_equal(expected.datasets[name], actual.datasets[name], check_exact=True)

    allowed_differences = {
        "orders": [
            "order_id",
            "session_id",
            "order_timestamp",
            "created_ts",
            "order_date",
            "fulfillment_channel",
        ],
        "order_items": ["order_id", "created_ts"],
        "payments": ["payment_id", "order_id", "payment_timestamp", "created_ts"],
        "shipments": [
            "shipment_id",
            "order_id",
            "handoff_ts",
            "estimated_delivery_ts",
            "created_ts",
        ],
    }
    for name, excluded in allowed_differences.items():
        pd.testing.assert_frame_equal(
            expected.datasets[name].drop(columns=excluded),
            actual.datasets[name].drop(columns=excluded),
            check_exact=True,
        )

    assert expected_stream.issue_records == actual_stream.issue_records
    assert expected_stream.topic_events.keys() == actual_stream.topic_events.keys()
    for topic in expected_stream.topic_events:
        expected_types = expected_stream.topic_events[topic]["event_type"].value_counts().sort_index()
        actual_types = actual_stream.topic_events[topic]["event_type"].value_counts().sort_index()
        pd.testing.assert_series_equal(expected_types, actual_types)
