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
    assign_customer_frequency_drift_timestamps,
    calculate_psi,
    generate_order_timestamps_with_drift,
    resolve_drift_window,
    summarize_drift_rates,
)
from vina_bim_shop.generators.drift_evidence import (
    _write_csv,
    build_feature_drift_alerts,
    build_feature_health_daily,
)
from vina_bim_shop.generators.labels import (
    LABEL_COLUMNS,
    build_feature_label_join,
    build_point_in_time_customer_features,
    build_purchase_labels,
    normalize_commerce_events_for_features,
)
from vina_bim_shop.generators.offline import orders as orders_module
from vina_bim_shop.generators.offline.generator import generate_offline
from vina_bim_shop.generators.profiles import random_timestamps
from vina_bim_shop.generators.streaming import generator as streaming_generator_module
from vina_bim_shop.generators.streaming.generator import generate_streaming_events
from vina_bim_shop.generators.writer import write_raw_outputs


STREAM_EVENT_ORDINAL = "_stream_event_ordinal"
STREAM_SESSION_ORDINAL = "_stream_session_ordinal"


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


def _legacy_and_drift_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[GeneratorConfig, Any, Any]:
    config = _config()
    actual_hook = orders_module.generate_order_timestamps_with_drift

    monkeypatch.setattr(orders_module, "generate_order_timestamps_with_drift", _legacy_timestamp_hook)
    legacy = generate_offline(config)
    monkeypatch.setattr(orders_module, "generate_order_timestamps_with_drift", actual_hook)
    drift = generate_offline(config)
    return config, legacy, drift


def _session_quality_projection(events: pd.DataFrame) -> pd.DataFrame:
    projection = events.copy()
    projection["created_delay_seconds"] = (
        pd.to_datetime(projection["created_ts"]) - pd.to_datetime(projection["event_timestamp"])
    ).dt.total_seconds()
    columns = [
        STREAM_EVENT_ORDINAL,
        STREAM_SESSION_ORDINAL,
        "event_type",
        "customer_id",
        "product_id",
        "device_type",
        "source",
        "primary_category",
        "payload",
        "is_late_arrival",
        "created_delay_seconds",
    ]
    return projection[columns].sort_values(
        [STREAM_EVENT_ORDINAL, STREAM_SESSION_ORDINAL],
        kind="stable",
    ).reset_index(drop=True)


def _synthetic_order_session_projection(
    commerce_events: pd.DataFrame,
    orders: pd.DataFrame,
) -> list[tuple[int, str, str]]:
    session_ordinals = {
        str(session_id): ordinal
        for ordinal, session_id in enumerate(orders["session_id"])
    }
    projection = []
    for event in commerce_events[
        commerce_events["event_type"].isin(
            {"session_started", "search_performed", "remove_from_cart"}
        )
    ].itertuples(index=False):
        session_id = str(event.correlation_ids.get("session_id"))
        if session_id not in session_ordinals:
            continue
        projection.append(
            (
                session_ordinals[session_id],
                str(event.event_type),
                json.dumps(event.payload, sort_keys=True, separators=(",", ":")),
            )
        )
    return sorted(projection)


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


def test_customer_frequency_assignment_is_deterministic_seeded_and_preserves_timestamps() -> None:
    timestamps = pd.Series(
        pd.to_datetime(
            [
                "2026-01-01T00:00:01Z",
                "2026-01-03T00:00:02Z",
                "2026-01-01T00:00:03Z",
                "2026-01-03T00:00:04Z",
                "2026-01-01T00:00:05Z",
                "2026-01-03T00:00:06Z",
                "2026-01-01T00:00:07Z",
                "2026-01-03T00:00:08Z",
            ]
        ),
        index=pd.Index(range(10, 18), name="row"),
        name="order_timestamp",
    )
    customer_ids = pd.Series(
        ["CUS-A", "CUS-A", "CUS-A", "CUS-B", "CUS-C", "CUS-D", "CUS-E", "CUS-F"],
        index=timestamps.index,
    )
    cutoff = pd.Timestamp("2026-01-02T00:00:00Z")

    first = assign_customer_frequency_drift_timestamps(
        timestamps,
        customer_ids,
        drift_start_ts=cutoff,
        random_seed=42,
    )
    second = assign_customer_frequency_drift_timestamps(
        timestamps,
        customer_ids,
        drift_start_ts=cutoff,
        random_seed=42,
    )
    different = assign_customer_frequency_drift_timestamps(
        timestamps,
        customer_ids,
        drift_start_ts=cutoff,
        random_seed=43,
    )

    pd.testing.assert_series_equal(first, second)
    assert not first.equals(different)
    assert first.index.equals(timestamps.index)
    assert first.name == timestamps.name
    assert first.dtype == timestamps.dtype
    assert int(first.lt(cutoff).sum()) == int(timestamps.lt(cutoff).sum())
    assert int(first.ge(cutoff).sum()) == int(timestamps.ge(cutoff).sum())
    pd.testing.assert_series_equal(
        first.sort_values(ignore_index=True),
        timestamps.sort_values(ignore_index=True),
    )


def test_customer_frequency_assignment_biases_repeat_customers_post_cutoff() -> None:
    customer_ids = pd.Series(
        ["CUS-REPEAT"] * 40 + [f"CUS-{index:03d}" for index in range(60)]
    )
    timestamps = pd.Series(
        pd.date_range("2026-01-01T00:00:00Z", periods=50, freq="min").tolist()
        + pd.date_range("2026-01-03T00:00:00Z", periods=50, freq="min").tolist()
    )
    cutoff = pd.Timestamp("2026-01-02T00:00:00Z")
    before = int(
        (
            customer_ids.eq("CUS-REPEAT")
            & pd.to_datetime(timestamps).ge(cutoff)
        ).sum()
    )

    assigned = assign_customer_frequency_drift_timestamps(
        timestamps,
        customer_ids,
        drift_start_ts=cutoff,
        random_seed=42,
    )
    after = int(
        (
            customer_ids.eq("CUS-REPEAT")
            & pd.to_datetime(assigned).ge(cutoff)
        ).sum()
    )

    assert before == 0
    assert after > before


def test_customer_frequency_assignment_uses_namespaced_hash_without_rng(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamps = pd.Series(
        pd.to_datetime(
            [
                "2026-01-01T00:00:00Z",
                "2026-01-03T00:00:00Z",
            ]
        )
    )
    customer_ids = pd.Series(["CUS-A", "CUS-B"])
    payloads: list[bytes] = []
    real_sha256 = hashlib.sha256

    def recording_sha256(payload: bytes = b"") -> Any:
        payloads.append(payload)
        return real_sha256(payload)

    def fail_rng(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("customer-frequency assignment must not use an RNG")

    monkeypatch.setattr(drift_module.hashlib, "sha256", recording_sha256)
    monkeypatch.setattr(drift_module.np.random, "default_rng", fail_rng)

    assign_customer_frequency_drift_timestamps(
        timestamps,
        customer_ids,
        drift_start_ts=pd.Timestamp("2026-01-02T00:00:00Z"),
        random_seed=42,
    )

    assert len(payloads) == len(timestamps)
    assert all(
        payload.startswith(b"section03-customer-frequency-assignment-v1\0")
        for payload in payloads
    )


@pytest.mark.parametrize(
    ("timestamps", "customer_ids", "message"),
    [
        (pd.Series(dtype="datetime64[ns]"), pd.Series(dtype="string"), "nonempty"),
        (
            pd.Series(pd.to_datetime(["2026-01-01", "2026-01-03"])),
            pd.Series(["CUS-A"]),
            "same length",
        ),
        (
            pd.Series(pd.to_datetime(["2026-01-01", "2026-01-03"])),
            pd.Series(["CUS-A", None]),
            "non-null",
        ),
        (
            pd.Series(["invalid", "2026-01-03"]),
            pd.Series(["CUS-A", "CUS-B"]),
            "valid timestamps",
        ),
        (
            pd.Series(pd.to_datetime(["2026-01-03", "2026-01-04"])),
            pd.Series(["CUS-A", "CUS-B"]),
            "pre- and post-drift",
        ),
    ],
)
def test_customer_frequency_assignment_rejects_invalid_inputs(
    timestamps: pd.Series,
    customer_ids: pd.Series,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        assign_customer_frequency_drift_timestamps(
            timestamps,
            customer_ids,
            drift_start_ts=pd.Timestamp("2026-01-02"),
            random_seed=42,
        )


def test_disabled_generation_skips_customer_frequency_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(_config(), drift=replace(_config().drift, enabled=False))

    def fail_assignment(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("disabled generation must not assign drift timestamps")

    monkeypatch.setattr(
        orders_module,
        "assign_customer_frequency_drift_timestamps",
        fail_assignment,
        raising=False,
    )

    result = generate_offline(config)

    assert result.datasets["orders"].shape[0] == config.entities["orders"]


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


def test_enabled_stream_quality_choices_follow_source_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, legacy, drift = _legacy_and_drift_offline(monkeypatch)
    captured: list[pd.DataFrame] = []

    def capture_session_events(
        config: GeneratorConfig,
        rng: np.random.Generator,
        session_events: pd.DataFrame,
        offline_datasets: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        del config, rng, offline_datasets
        captured.append(session_events.copy())
        return {}

    monkeypatch.setattr(streaming_generator_module, "_build_topic_events", capture_session_events)
    generate_streaming_events(config, legacy.datasets)
    generate_streaming_events(config, drift.datasets)

    assert len(captured) == 2
    pd.testing.assert_frame_equal(
        _session_quality_projection(captured[0]),
        _session_quality_projection(captured[1]),
        check_exact=True,
    )


def test_enabled_synthetic_commerce_choices_follow_source_lineage_without_leaks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, legacy, drift = _legacy_and_drift_offline(monkeypatch)

    legacy_stream = generate_streaming_events(config, legacy.datasets)
    drift_stream = generate_streaming_events(config, drift.datasets)

    assert _synthetic_order_session_projection(
        legacy_stream.topic_events["commerce_events"],
        legacy.datasets["orders"],
    ) == _synthetic_order_session_projection(
        drift_stream.topic_events["commerce_events"],
        drift.datasets["orders"],
    )
    for frame in drift_stream.topic_events.values():
        serialized = json.dumps(frame.to_dict("records"), default=str)
        assert STREAM_EVENT_ORDINAL not in frame.columns
        assert STREAM_SESSION_ORDINAL not in frame.columns
        assert STREAM_EVENT_ORDINAL not in serialized
        assert STREAM_SESSION_ORDINAL not in serialized


def test_disabled_streaming_skips_stable_lineage_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(_config(), drift=replace(_config().drift, enabled=False))
    offline = generate_offline(config)

    def fail_if_called(events: pd.DataFrame) -> pd.DataFrame:
        del events
        raise AssertionError("disabled streaming must retain the legacy ordering path")

    monkeypatch.setattr(
        streaming_generator_module,
        "_attach_stable_stream_lineage",
        fail_if_called,
        raising=False,
    )

    result = generate_streaming_events(config, offline.datasets)

    assert result.topic_events


def _unit_window() -> DriftWindow:
    return DriftWindow(
        start_ts=pd.Timestamp("2026-01-01T00:00:00Z"),
        end_ts=pd.Timestamp("2026-01-15T00:00:00Z"),
        drift_start_ts=pd.Timestamp("2026-01-08T12:00:00Z"),
        feature_cutoff_ts=pd.Timestamp("2026-01-08T00:00:00Z"),
        label_end_ts=pd.Timestamp("2026-01-15T00:00:00Z"),
        baseline_date=date(2026, 1, 7),
    )


def test_purchase_labels_use_exact_horizon_and_cutoff_known_cohort() -> None:
    window = _unit_window()
    customers = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3", "C4"],
            "created_ts": [
                "2026-01-01T00:00:00Z",
                "2026-01-08T00:00:00Z",
                "2026-01-07T00:00:00Z",
                "2026-01-08T00:00:01Z",
            ],
        }
    )
    payments = pd.DataFrame(
        {
            "payment_id": [f"P{i}" for i in range(8)],
            "customer_id": ["C1", "C1", "C1", "C2", "C2", "C3", "C3", "C4"],
            "payment_timestamp": [
                "2026-01-07T23:59:59Z",
                "2026-01-08T00:00:00Z",
                "2026-01-08T00:00:01Z",
                "2026-01-15T00:00:00Z",
                "2026-01-15T00:00:01Z",
                "2026-01-09T00:00:00Z",
                "2026-01-10T00:00:00Z",
                "2026-01-09T00:00:00Z",
            ],
            "created_ts": [
                "2026-01-07T23:59:59Z",
                "2026-01-08T00:00:00Z",
                "2026-01-08T00:00:01Z",
                "2026-01-15T00:00:00Z",
                "2026-01-15T00:00:01Z",
                "2026-01-09T00:00:00Z",
                "2026-01-16T00:00:00Z",
                "2026-01-09T00:00:00Z",
            ],
            "payment_status": [
                "success",
                "success",
                "success",
                "success",
                "success",
                "failed",
                "success",
                "success",
            ],
        }
    )

    labels = build_purchase_labels(customers, payments, window=window)

    assert tuple(labels.columns) == LABEL_COLUMNS
    assert labels.to_dict("records") == [
        {"id": "C1", "label": 1},
        {"id": "C2", "label": 1},
        {"id": "C3", "label": 0},
    ]
    assert str(labels["id"].dtype) == "string"
    assert labels["label"].dtype == np.dtype("int8")


@pytest.mark.parametrize(
    "customers",
    [
        pd.DataFrame({"customer_id": ["C1", "C1"], "created_ts": ["2026-01-01", "2026-01-02"]}),
        pd.DataFrame({"customer_id": ["C1", None], "created_ts": ["2026-01-01", "2026-01-02"]}),
        pd.DataFrame({"customer_id": ["C1"], "created_ts": ["not-a-timestamp"]}),
    ],
)
def test_purchase_labels_reject_invalid_customer_identity_or_time(
    customers: pd.DataFrame,
) -> None:
    payments = pd.DataFrame(
        columns=["payment_id", "customer_id", "payment_timestamp", "created_ts", "payment_status"]
    )

    with pytest.raises(ValueError):
        build_purchase_labels(customers, payments, window=_unit_window())


def test_point_in_time_features_exclude_future_and_keep_inactive_customers() -> None:
    window = _unit_window()
    customers = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "FUTURE"],
            "created_ts": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "2026-01-08T00:00:01Z",
            ],
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": ["O1", "O2", "O3", "O4"],
            "customer_id": ["C1", "C1", "C1", "FUTURE"],
            "order_timestamp": [
                "2026-01-07T23:00:00Z",
                "2026-01-08T00:00:01Z",
                "2026-01-07T22:00:00Z",
                "2026-01-07T20:00:00Z",
            ],
            "created_ts": [
                "2026-01-07T23:00:00Z",
                "2026-01-08T00:00:01Z",
                "2026-01-08T00:00:01Z",
                "2026-01-07T20:00:00Z",
            ],
            "primary_category": ["FMCG", "ELHA", "Fashion", "FMCG"],
        }
    )
    payments = pd.DataFrame(
        {
            "payment_id": ["P1", "P2"],
            "order_id": ["O1", "O1"],
            "customer_id": ["C1", "C1"],
            "payment_timestamp": ["2026-01-07T23:05:00Z", "2026-01-07T23:06:00Z"],
            "created_ts": ["2026-01-07T23:05:00Z", "2026-01-08T00:00:01Z"],
            "payment_status": ["success", "success"],
            "amount": [25.0, 999.0],
        }
    )
    raw_events = pd.DataFrame(
        {
            "event_id": ["E1", "E2", "E3", "E4"],
            "event_type": ["product_viewed", "add_to_cart", "order_placed", "add_to_cart"],
            "event_timestamp": [
                "2026-01-07T23:30:00Z",
                "2026-01-07T23:45:00Z",
                "2026-01-07T23:50:00Z",
                "2026-01-07T23:40:00Z",
            ],
            "created_ts": [
                "2026-01-07T23:31:00Z",
                "2026-01-08T00:00:01Z",
                "2026-01-07T23:51:00Z",
                "2026-01-07T23:41:00Z",
            ],
            "correlation_ids": [
                {"customer_id": "C1"},
                {"customer_id": "C1"},
                {"customer_id": "C1", "order_id": "O1"},
                {"customer_id": "C1"},
            ],
            "payload": [{}, {}, {}, {}],
        }
    )
    events = normalize_commerce_events_for_features({"commerce_events": raw_events})

    features = build_point_in_time_customer_features(
        customers,
        orders,
        payments,
        events,
        window=window,
    )

    assert features["id"].tolist() == ["C1", "C2"]
    active = features.set_index("id").loc["C1"]
    assert active["f_customer_total_orders_90d"] == 1
    assert active["f_customer_paid_revenue_90d"] == 25.0
    assert active["f_customer_avg_order_value_90d"] == 25.0
    assert active["f_customer_distinct_categories_90d"] == 1
    assert active["f_stream_views_60m"] == 1
    assert active["f_stream_add_to_cart_60m"] == 1
    assert active["f_stream_order_placed_60m"] == 1
    assert active["f_stream_cart_to_purchase_ratio_60m"] == 1.0
    inactive = features.set_index("id").loc["C2"]
    numeric = [column for column in features if column.startswith("f_")]
    assert (inactive[numeric].astype(float) == 0.0).all()
    assert (features["event_timestamp"] == window.feature_cutoff_ts).all()
    assert (features["created"] == window.feature_cutoff_ts).all()


def test_feature_label_join_is_exact_and_one_to_one() -> None:
    labels = pd.DataFrame({"id": pd.Series(["C1", "C2"], dtype="string"), "label": pd.Series([1, 0], dtype="int8")})
    features = pd.DataFrame(
        {
            "id": pd.Series(["C1", "C2"], dtype="string"),
            "event_timestamp": pd.to_datetime(["2026-01-08T00:00:00Z"] * 2),
            "f_customer_total_orders_90d": [1, 0],
            "f_customer_paid_revenue_90d": [25.0, 0.0],
            "f_customer_avg_order_value_90d": [25.0, 0.0],
            "f_customer_distinct_categories_90d": [1, 0],
            "f_stream_views_60m": [1, 0],
            "f_stream_add_to_cart_60m": [0, 0],
            "f_stream_checkout_started_60m": [0, 0],
            "f_stream_order_placed_60m": [1, 0],
            "f_stream_cart_to_purchase_ratio_60m": [1.0, 0.0],
            "created": pd.to_datetime(["2026-01-08T00:00:00Z"] * 2),
        }
    )

    training = build_feature_label_join(labels, features)

    assert list(training.columns) == [
        "id",
        "event_timestamp",
        "label",
        "f_customer_total_orders_90d",
        "f_customer_paid_revenue_90d",
        "f_customer_avg_order_value_90d",
        "f_customer_distinct_categories_90d",
        "f_stream_views_60m",
        "f_stream_add_to_cart_60m",
        "f_stream_checkout_started_60m",
        "f_stream_order_placed_60m",
        "f_stream_cart_to_purchase_ratio_60m",
        "created",
    ]
    assert training[["id", "label"]].equals(labels)
    with pytest.raises(ValueError):
        build_feature_label_join(labels, features.iloc[[0]])


def test_training_csv_serialization_uses_fixed_twelve_decimal_places(tmp_path: Path) -> None:
    output = tmp_path / "training.csv"
    _write_csv(output, pd.DataFrame({"value": [1.2345678901234]}), fixed_decimal=True)

    assert output.read_text(encoding="utf-8").splitlines()[1] == "1.234567890123"


def test_health_csv_serialization_remains_fixed_twelve_decimal_places(tmp_path: Path) -> None:
    output = tmp_path / "health.csv"
    _write_csv(output, pd.DataFrame({"value": [1.2345678901234]}), health=True)

    assert output.read_text(encoding="utf-8").splitlines()[1] == "1.234567890123"


@pytest.mark.parametrize(
    ("baseline", "current", "expected_zero"),
    [
        ([0, 1, 2, 3], [0, 1, 2, 3], True),
        ([0, 0, 0, 0], [0, 1, 2, 3], False),
        ([0, 0, 1, 1, 2, 2], [0, 0, 0, 2, 2, 2], False),
    ],
)
def test_calculate_psi_is_finite_and_handles_repeated_or_zero_bins(
    baseline: list[float],
    current: list[float],
    expected_zero: bool,
) -> None:
    result = calculate_psi(pd.Series(baseline), pd.Series(current))

    assert np.isfinite(result)
    assert result >= 0
    assert (result == 0.0) is expected_zero


@pytest.mark.parametrize(
    ("baseline", "current", "kwargs"),
    [
        ([], [1], {}),
        ([1], [], {}),
        ([np.nan, np.inf], [1], {}),
        ([1], [1], {"quantile_bins": 1}),
        ([1], [1], {"epsilon": 0.0}),
        ([1], [1], {"epsilon": 1.0}),
    ],
)
def test_calculate_psi_rejects_invalid_inputs(
    baseline: list[float],
    current: list[float],
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        calculate_psi(pd.Series(baseline), pd.Series(current), **kwargs)


def test_health_uses_fixed_cohort_complete_windows_and_inclusive_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _unit_window()
    customers = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "LATE"],
            "created_ts": [
                "2026-01-01T00:00:00Z",
                "2026-01-07T23:59:59Z",
                "2026-01-08T00:00:00Z",
            ],
        }
    )
    orders = pd.DataFrame(
        {
            "order_id": ["OLD", "B1", "C1", "LATE"],
            "customer_id": ["C1", "C1", "C1", "LATE"],
            "order_timestamp": [
                "2025-12-31T23:59:59Z",
                "2026-01-07T12:00:00Z",
                "2026-01-08T12:00:00Z",
                "2026-01-08T12:00:00Z",
            ],
            "created_ts": [
                "2025-12-31T23:59:59Z",
                "2026-01-07T12:00:00Z",
                "2026-01-08T12:00:00Z",
                "2026-01-08T12:00:00Z",
            ],
        }
    )
    observed = iter([0.0, 0.099999, 0.10, 0.149999, 0.15, 0.2, 0.0, 0.0, 0.0])
    monkeypatch.setattr(
        "vina_bim_shop.generators.drift_evidence.calculate_psi",
        lambda baseline, current: next(observed),
    )

    health = build_feature_health_daily(
        customers,
        orders,
        window=window,
        drift=_config().drift,
    )

    assert health["customer_count"].eq(2).all()
    assert health["monitoring_date"].min() == date(2026, 1, 7)
    assert health["monitoring_date"].max() == date(2026, 1, 15)
    assert health["drift_status"].tolist()[:5] == [
        "stable",
        "stable",
        "warning",
        "warning",
        "alert",
    ]
    alerts = build_feature_drift_alerts(health, alert_threshold=0.15)
    assert (alerts["psi_value"] >= 0.15).all()
    assert alerts["action"].eq("Investigate customer_order_frequency drift").all()


def test_normalized_commerce_events_rank_duplicates_and_reject_ambiguous_ties() -> None:
    base = {
        "event_id": "E1",
        "event_type": "product_viewed",
        "event_timestamp": "2026-01-07T23:00:00Z",
        "created_ts": "2026-01-07T23:01:00Z",
        "ingest_ts": "2026-01-07T23:02:00Z",
        "correlation_ids": {"customer_id": "C1", "product_id": "P1"},
        "payload": {"primary_category": "FMCG"},
    }
    older = dict(base, created_ts="2026-01-07T23:00:30Z")
    winner = dict(base, correlation_ids='{"customer_id":"C2","product_id":"P1"}')

    normalized = normalize_commerce_events_for_features(
        {"commerce_events": pd.DataFrame([older, winner, winner])}
    )

    assert len(normalized) == 1
    assert normalized.loc[0, "customer_id"] == "C2"
    conflicting = dict(winner, payload={"primary_category": "ELHA"})
    with pytest.raises(ValueError, match="ambiguous normalized winner"):
        normalize_commerce_events_for_features(
            {"commerce_events": pd.DataFrame([winner, conflicting])}
        )


def test_smoke_normalized_stream_preserves_boundary_offsets_without_ratio_claim() -> None:
    config = _config(scale="smoke")
    window = resolve_drift_window(config)
    offline = generate_offline(config)
    streaming = generate_streaming_events(config, offline.datasets)
    normalized = normalize_commerce_events_for_features(streaming.topic_events)
    orders = offline.datasets["orders"][["order_id", "order_timestamp"]].copy()
    order_events = normalized.dropna(subset=["order_id"]).merge(
        orders,
        on="order_id",
        how="inner",
        validate="many_to_one",
    )
    event_times = pd.to_datetime(order_events["event_timestamp"], utc=True)
    order_times = pd.to_datetime(order_events["order_timestamp"], utc=True)
    offsets = (event_times - order_times).dt.total_seconds()

    assert offsets.between(-240, 2100, inclusive="both").all()
    cutoff = pd.Timestamp(window.drift_start_ts)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")
    far_from_cutoff = (order_times - cutoff).abs().dt.total_seconds().gt(2100)
    assert (
        event_times.loc[far_from_cutoff].ge(cutoff)
        == order_times.loc[far_from_cutoff].ge(cutoff)
    ).all()
    crossing = event_times.ge(cutoff) != order_times.ge(cutoff)
    assert (order_times.loc[crossing] - cutoff).abs().dt.total_seconds().le(2100).all()
