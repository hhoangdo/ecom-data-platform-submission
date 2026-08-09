from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from vina_bim_shop.llm.api.drift import app as drift_app
from vina_bim_shop.llm.contracts import DriftDetectRequest, FeatureHealthPoint, Section03FeatureRow, TimeWindow
from vina_bim_shop.llm.drift import (
    DEPENDENCY_TIMEOUT_SECONDS,
    DependencyTimeoutError,
    DriftDetectionService,
    FeatureUnavailableError,
    SECTION03_MANIFEST_SHA256,
)


UTC = timezone.utc
BASELINE_DATE = date(2026, 4, 10)
BASELINE = TimeWindow(
    start=datetime(2026, 4, 4, tzinfo=UTC), end=datetime(2026, 4, 11, tzinfo=UTC)
)


def _point(day: date, psi: float, *, mean: float | None = None, count: int = 12) -> FeatureHealthPoint:
    status = "alert" if psi >= 0.15 else "warning" if psi >= 0.10 else "stable"
    return FeatureHealthPoint(
        monitoring_date=day,
        feature_name="f_customer_order_frequency_7d",
        window_days=7,
        baseline_date=BASELINE_DATE,
        customer_count=count,
        mean_value=1.0 + psi if mean is None else mean,
        psi_vs_baseline=psi,
        drift_status=status,
    )


def _published_points(days: int, *, psi: float = 0.05) -> list[FeatureHealthPoint]:
    return [_point(BASELINE_DATE, 0.0, mean=3.25)] + [
        _point(BASELINE_DATE + timedelta(days=offset), psi)
        for offset in range(1, days + 1)
    ]


def _request(days: int, *, id: str | None = None) -> DriftDetectRequest:
    return DriftDetectRequest(
        id=id,
        baseline_window=BASELINE,
        candidate_window=TimeWindow(
            start=datetime(2026, 4, 11, tzinfo=UTC),
            end=datetime(2026, 4, 11, tzinfo=UTC) + timedelta(days=days),
        ),
    )


def _context() -> Section03FeatureRow:
    return Section03FeatureRow(
        id="fixture-customer-001",
        event_timestamp=datetime(2026, 4, 24, 23, 59, tzinfo=UTC),
        label=1,
        f_customer_total_orders_90d=2,
        f_customer_paid_revenue_90d=3.0,
        f_customer_avg_order_value_90d=1.5,
        f_customer_distinct_categories_90d=2,
        f_stream_views_60m=4,
        f_stream_add_to_cart_60m=3,
        f_stream_checkout_started_60m=2,
        f_stream_order_placed_60m=1,
        f_stream_cart_to_purchase_ratio_60m=0.25,
        created=datetime(2026, 4, 24, 23, 59, tzinfo=UTC),
    )


class FakeFeast:
    def __init__(
        self,
        points: list[FeatureHealthPoint],
        *,
        delay: float = 0.0,
        health_errors: list[Exception] | None = None,
        context: Section03FeatureRow | None = None,
    ) -> None:
        self.points = points
        self.delay = delay
        self.health_errors = health_errors or []
        self.context = context
        self.calls = 0
        self.snapshot_as_of: datetime | None = None

    async def read_feature_health(self, *, feature_name: str, window: TimeWindow):
        del feature_name, window
        self.calls += 1
        if self.health_errors:
            raise self.health_errors.pop(0)
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.points

    async def read_customer_snapshot(self, *, id: str, as_of: datetime):
        del id
        self.snapshot_as_of = as_of
        return self.context

    async def active_section03_manifest_hash(self) -> str | None:
        return "a" * 64


@pytest.mark.asyncio
async def test_detect_uses_the_fixed_baseline_row_and_is_deterministic_for_a_fixed_clock() -> None:
    points = _published_points(2)
    points[1] = _point(date(2026, 4, 11), 0.10, mean=1.10)
    points[2] = _point(date(2026, 4, 12), 0.15, mean=1.15)
    service = DriftDetectionService(
        feast=FakeFeast(points), baseline_date=BASELINE_DATE,
        clock=lambda: datetime(2026, 5, 2, tzinfo=UTC),
    )
    first = await service.detect(_request(2, id="missing-customer"))
    second = await service.detect(_request(2, id="missing-customer"))
    assert first == second
    assert first.baseline_mean == 3.25
    assert first.candidate_mean == 1.15
    assert first.psi == 0.15
    assert first.status == "alert"
    assert first.customer_context is None


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [1, 7, 30])
async def test_detect_accepts_exact_complete_candidate_day_boundaries(days: int) -> None:
    service = DriftDetectionService(
        feast=FakeFeast(_published_points(days)), baseline_date=BASELINE_DATE,
        published_monitoring_end=BASELINE_DATE + timedelta(days=days),
    )
    response = await service.detect(_request(days))
    assert response.candidate_day_count == days


def test_zero_day_candidate_window_is_rejected_by_the_contract() -> None:
    with pytest.raises(ValidationError, match="window start"):
        _request(0)


@pytest.mark.asyncio
async def test_thirty_one_day_candidate_window_is_rejected() -> None:
    service = DriftDetectionService(
        feast=FakeFeast(_published_points(31)), baseline_date=BASELINE_DATE,
        published_monitoring_end=BASELINE_DATE + timedelta(days=31),
    )
    with pytest.raises(ValueError, match="1-30"):
        await service.detect(_request(31))


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["missing", "duplicate", "cohort", "out_of_range"])
async def test_detect_fails_closed_for_incomplete_or_unstable_published_health(fault: str) -> None:
    points = _published_points(2)
    if fault == "missing":
        points.pop()
    elif fault == "duplicate":
        points.append(_point(date(2026, 4, 12), 0.05))
    elif fault == "cohort":
        points[2] = _point(date(2026, 4, 12), 0.05, count=11)
    else:
        points.append(_point(date(2026, 4, 13), 0.05))
    service = DriftDetectionService(feast=FakeFeast(points), baseline_date=BASELINE_DATE)
    with pytest.raises(FeatureUnavailableError, match="feature_unavailable"):
        await service.detect(_request(2))


@pytest.mark.asyncio
@pytest.mark.parametrize(("psi", "status"), [(0.099, "stable"), (0.10, "warning"), (0.15, "alert")])
async def test_detect_uses_exact_psi_status_thresholds(psi: float, status: str) -> None:
    service = DriftDetectionService(feast=FakeFeast(_published_points(1, psi=psi)), baseline_date=BASELINE_DATE)
    response = await service.detect(_request(1))
    assert response.status == status
    assert response.drift_detected is (status != "stable")


@pytest.mark.asyncio
async def test_detect_breaks_peak_ties_by_latest_monitoring_date() -> None:
    points = _published_points(2)
    points[1] = _point(date(2026, 4, 11), 0.15, mean=2.0)
    points[2] = _point(date(2026, 4, 12), 0.15, mean=4.0)
    response = await DriftDetectionService(feast=FakeFeast(points), baseline_date=BASELINE_DATE).detect(_request(2))
    assert response.candidate_mean == 4.0


@pytest.mark.asyncio
async def test_detect_retries_one_connection_error_and_respects_the_exact_timeout() -> None:
    retried = FakeFeast(_published_points(1), health_errors=[ConnectionError("once")])
    response = await DriftDetectionService(feast=retried, baseline_date=BASELINE_DATE).detect(_request(1))
    assert response.candidate_day_count == 1
    assert retried.calls == 2

    timeout = FakeFeast(_published_points(1), delay=1.6)
    assert DEPENDENCY_TIMEOUT_SECONDS == 1.5
    with pytest.raises(DependencyTimeoutError, match="dependency_timeout"):
        await DriftDetectionService(feast=timeout, baseline_date=BASELINE_DATE).detect(_request(1))
    assert timeout.calls == 1


@pytest.mark.asyncio
async def test_optional_id_is_cutoff_safe_and_absence_never_changes_population() -> None:
    feast = FakeFeast(_published_points(1), context=_context())
    service = DriftDetectionService(feast=feast, baseline_date=BASELINE_DATE)
    present = await service.detect(_request(1, id="fixture-customer-001"))
    absent = await DriftDetectionService(feast=FakeFeast(_published_points(1)), baseline_date=BASELINE_DATE).detect(_request(1, id="missing"))
    assert feast.snapshot_as_of == present.candidate_window.end
    assert present.customer_context == _context()
    assert absent.customer_context is None
    assert absent.population_size == present.population_size
    assert absent.psi == present.psi


def test_api_exposes_liveness_feature_unavailable_and_malformed_id() -> None:
    original = getattr(drift_app.state, "drift_service", None)
    try:
        drift_app.state.drift_service = DriftDetectionService()
        client = TestClient(drift_app)
        assert client.get("/healthz").status_code == 200
        body = {"baseline_window": {"start": "2026-04-04T00:00:00Z", "end": "2026-04-11T00:00:00Z"}, "candidate_window": {"start": "2026-04-11T00:00:00Z", "end": "2026-04-12T00:00:00Z"}}
        assert client.post("/v1/drift/detect", json=body).status_code == 409
        body["id"] = ""
        malformed = client.post("/v1/drift/detect", json=body)
        assert malformed.status_code == 422
        assert malformed.json()["code"] == "validation_error"
        assert 'edai2_drift_requests_total{route="/v1/drift/detect",service="edai2-drift-agent",status="422"}' in client.get("/metrics").text
    finally:
        drift_app.state.drift_service = original


def test_readyz_requires_the_exact_verified_active_hash() -> None:
    original = drift_app.state.drift_service
    try:
        unavailable = FakeFeast([])
        drift_app.state.drift_service = DriftDetectionService(feast=unavailable, baseline_date=BASELINE_DATE)
        assert TestClient(drift_app).get("/readyz").status_code == 503

        class VerifiedFeast(FakeFeast):
            async def active_section03_manifest_hash(self) -> str | None:
                return SECTION03_MANIFEST_SHA256

        drift_app.state.drift_service = DriftDetectionService(feast=VerifiedFeast([]), baseline_date=BASELINE_DATE)
        assert TestClient(drift_app).get("/readyz").status_code == 200
    finally:
        drift_app.state.drift_service = original


def test_readyz_fails_closed_for_an_unexpected_dependency_error() -> None:
    class BrokenFeast(FakeFeast):
        async def active_section03_manifest_hash(self) -> str | None:
            raise RuntimeError("database socket reset")

    original = drift_app.state.drift_service
    try:
        drift_app.state.drift_service = DriftDetectionService(
            feast=BrokenFeast([]), baseline_date=BASELINE_DATE
        )
        response = TestClient(drift_app, raise_server_exceptions=False).get("/readyz")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"
    finally:
        drift_app.state.drift_service = original
