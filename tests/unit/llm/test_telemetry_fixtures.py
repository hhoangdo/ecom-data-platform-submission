from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
REVISION = "c" * 40
LEASE_STARTED_AT = "2026-10-18T00:00:00+00:00"
KINDS = ["http", "compute", "llm", "agents", "logs", "traces", "alerts"]


def _load_smoke():
    path = ROOT / "scripts/llm/smoke_release.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_capture():
    path = ROOT / "scripts/qa/capture_edai2_evidence.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _queries(smoke):
    metrics = {name: {"labels": {"service": "api", "route": "chat", "log_scope": "application"}, "samples": 3} for name in smoke.REQUIRED_TELEMETRY_METRICS}

    def prom_query(expr: str) -> dict:
        return {"series": metrics}

    def loki_query(scope: str) -> dict:
        return {"count": 4 if scope == "application" else 2}

    def tempo_query() -> dict:
        return {"spans": [{"span": span, "parent": parent} for span, parent in smoke.TRACE_CHAIN]}

    alerts = {
        name: {"pending_at": "2026-10-18T00:10:00+00:00", "firing_at": "2026-10-18T00:15:00+00:00", "recovered_at": "2026-10-18T00:20:00+00:00"}
        for name in smoke.ALERT_THRESHOLDS
    }
    return prom_query, loki_query, tempo_query, alerts


def test_telemetry_fixtures_collect_and_verify() -> None:
    """Required metrics, separated scopes, full trace, and alert cycles verify."""
    smoke = _load_smoke()
    prom_query, loki_query, tempo_query, alerts = _queries(smoke)
    payload = smoke.generate_telemetry_fixtures(
        prom_query=prom_query, loki_query=loki_query, tempo_query=tempo_query,
        alert_states=alerts, kinds=KINDS, revision=REVISION, lease_started_at=LEASE_STARTED_AT,
    )
    assert payload["revision"] == REVISION
    result = smoke.verify_telemetry_evidence(payload, lease_started_at=LEASE_STARTED_AT, root=ROOT)
    assert result["metrics"] == len(smoke.REQUIRED_TELEMETRY_METRICS)


def test_telemetry_contracts_match_observability_fixtures() -> None:
    """Metric, label, and trace contracts must stay identical across modules."""
    smoke, capture = _load_smoke(), _load_capture()
    assert smoke.STABLE_LABELS == capture.STABLE_LABELS
    assert [(span, parent) for span, parent in smoke.TRACE_CHAIN] == [
        (span["span"], span["parent"]) for span in capture.TRACE_FIXTURE
    ]
    import json
    import re

    text = " ".join(
        target.get("expr", "")
        for name in ("http", "compute", "agents", "llm", "ab")
        for panel in json.loads((ROOT / f"infra/observability/grafana/dashboards/{name}.json").read_text(encoding="utf-8"))["panels"]
        for target in panel.get("targets", [])
    )
    names = set(re.findall(r"[a-z_][a-z0-9_]*(?:_total|_seconds|_bucket|_ratio|_score|_samples)", text))
    assert names <= set(smoke.REQUIRED_TELEMETRY_METRICS), names - set(smoke.REQUIRED_TELEMETRY_METRICS)


def test_verify_telemetry_rejects_missing_metric() -> None:
    smoke = _load_smoke()
    prom_query, loki_query, tempo_query, alerts = _queries(smoke)
    payload = smoke.generate_telemetry_fixtures(
        prom_query=prom_query, loki_query=loki_query, tempo_query=tempo_query,
        alert_states=alerts, kinds=KINDS, revision=REVISION, lease_started_at=LEASE_STARTED_AT,
    )
    del payload["metrics"][smoke.REQUIRED_TELEMETRY_METRICS[0]]
    with pytest.raises(ValueError, match="metric"):
        smoke.verify_telemetry_evidence(payload, lease_started_at=LEASE_STARTED_AT, root=ROOT)


def test_verify_telemetry_rejects_merged_scopes_and_unknown_label() -> None:
    smoke = _load_smoke()
    prom_query, loki_query, tempo_query, alerts = _queries(smoke)
    payload = smoke.generate_telemetry_fixtures(
        prom_query=prom_query, loki_query=loki_query, tempo_query=tempo_query,
        alert_states=alerts, kinds=KINDS, revision=REVISION, lease_started_at=LEASE_STARTED_AT,
    )
    payload["log_scopes"] = {"application": 4}
    with pytest.raises(ValueError, match="scope"):
        smoke.verify_telemetry_evidence(payload, lease_started_at=LEASE_STARTED_AT, root=ROOT)
    payload["log_scopes"] = {"application": 4, "system": 2}
    first = next(iter(payload["metrics"]))
    payload["metrics"][first]["labels"]["customer_id"] = "42"
    with pytest.raises(ValueError, match="label"):
        smoke.verify_telemetry_evidence(payload, lease_started_at=LEASE_STARTED_AT, root=ROOT)


def test_verify_telemetry_rejects_broken_trace_and_alert_disorder() -> None:
    smoke = _load_smoke()
    prom_query, loki_query, tempo_query, alerts = _queries(smoke)
    payload = smoke.generate_telemetry_fixtures(
        prom_query=prom_query, loki_query=loki_query, tempo_query=tempo_query,
        alert_states=alerts, kinds=KINDS, revision=REVISION, lease_started_at=LEASE_STARTED_AT,
    )
    payload["trace"]["spans"][-1]["parent"] = None
    with pytest.raises(ValueError, match="trace"):
        smoke.verify_telemetry_evidence(payload, lease_started_at=LEASE_STARTED_AT, root=ROOT)
    payload["trace"]["spans"][-1]["parent"] = "retrieval/drift API"
    first_alert = next(iter(payload["alerts"]))
    payload["alerts"][first_alert]["recovered_at"] = "2026-10-18T00:01:00+00:00"
    with pytest.raises(ValueError, match="alert"):
        smoke.verify_telemetry_evidence(payload, lease_started_at=LEASE_STARTED_AT, root=ROOT)
